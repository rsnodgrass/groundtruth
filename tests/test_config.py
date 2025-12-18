"""Tests for groundtruth.config module."""

from pathlib import Path
from typing import Any

import pytest
import yaml

from groundtruth.config import (
    Decision,
    ExtractionResult,
    TrackerConfig,
    _parse_markdown_participants,
    decisions_to_csv_rows,
    get_default_config,
    get_json_schema_for_extraction,
    load_config,
    merge_frameworks,
    save_config,
)


class TestDecisionModel:
    """Tests for Decision model validation."""

    def test_valid_decision(self, sample_decision_data: dict[str, Any]) -> None:
        """Test creating a valid Decision object."""
        decision = Decision(**sample_decision_data)
        assert decision.category == "Technical Architecture"
        assert decision.significance == 2
        assert decision.status == "Agreed"
        assert decision.title == "Use PostgreSQL for data storage"
        assert decision.agreements["Alice"] == "Yes"

    def test_decision_with_defaults(self) -> None:
        """Test Decision with optional fields using defaults."""
        decision = Decision(
            category="Security",
            significance=1,
            status="Needs Clarification",
            title="Implement OAuth2",
            description="Need to add OAuth2 authentication",
            decision="No decision reached",
            agreements={"Alice": "Yes"},
        )
        assert decision.notes == ""
        assert decision.meeting_date == ""
        assert decision.meeting_reference == ""

    def test_invalid_significance_too_low(self) -> None:
        """Test that significance < 1 raises validation error."""
        with pytest.raises(Exception):
            Decision(
                category="Tech",
                significance=0,
                status="Agreed",
                title="Test",
                description="Test",
                decision="Test",
                agreements={"Alice": "Yes"},
            )

    def test_invalid_significance_too_high(self) -> None:
        """Test that significance > 5 raises validation error."""
        with pytest.raises(Exception):
            Decision(
                category="Tech",
                significance=6,
                status="Agreed",
                title="Test",
                description="Test",
                decision="Test",
                agreements={"Alice": "Yes"},
            )

    def test_invalid_status(self) -> None:
        """Test that invalid status raises validation error."""
        with pytest.raises(Exception):
            Decision(
                category="Tech",
                significance=3,
                status="Invalid Status",  # type: ignore
                title="Test",
                description="Test",
                decision="Test",
                agreements={"Alice": "Yes"},
            )

    def test_invalid_agreement_value(self) -> None:
        """Test that invalid agreement value raises validation error."""
        with pytest.raises(Exception):
            Decision(
                category="Tech",
                significance=3,
                status="Agreed",
                title="Test",
                description="Test",
                decision="Test",
                agreements={"Alice": "Maybe"},  # type: ignore
            )


class TestExtractionResultModel:
    """Tests for ExtractionResult model."""

    def test_empty_extraction_result(self) -> None:
        """Test creating an empty ExtractionResult."""
        result = ExtractionResult(decisions=[])
        assert result.decisions == []
        assert result.participants_detected == []

    def test_extraction_result_with_decisions(self, sample_decision: Decision) -> None:
        """Test ExtractionResult with decisions and participants."""
        result = ExtractionResult(
            decisions=[sample_decision],
            participants_detected=["Alice", "Bob", "Carol"],
        )
        assert len(result.decisions) == 1
        assert len(result.participants_detected) == 3
        assert "Alice" in result.participants_detected


class TestDecisionsToCSVRows:
    """Tests for decisions_to_csv_rows conversion function."""

    def test_empty_decisions(self) -> None:
        """Test converting empty decision list."""
        rows = decisions_to_csv_rows([], ["Alice", "Bob"])
        assert len(rows) == 1  # header only
        assert rows[0][0] == "Category"
        assert "Alice Agreed" in rows[0]
        assert "Bob Agreed" in rows[0]

    def test_single_decision(self, sample_decision: Decision) -> None:
        """Test converting single decision to CSV rows."""
        rows = decisions_to_csv_rows([sample_decision], ["Alice", "Bob", "Carol"])
        assert len(rows) == 2  # header + 1 data row

        # check header
        assert rows[0][0] == "Category"
        assert "Alice Agreed" in rows[0]
        assert "Bob Agreed" in rows[0]
        assert "Carol Agreed" in rows[0]

        # check data row
        data_row = rows[1]
        assert data_row[0] == "Technical Architecture"
        assert data_row[1] == "2"
        assert data_row[2] == "Agreed"
        assert data_row[3] == "Use PostgreSQL for data storage"

    def test_multiple_decisions_sorted(self) -> None:
        """Test that decisions are sorted by category then significance."""
        decision1 = Decision(
            category="Security",
            significance=3,
            status="Agreed",
            title="D1",
            description="D1",
            decision="D1",
            agreements={"Alice": "Yes"},
        )
        decision2 = Decision(
            category="Security",
            significance=1,
            status="Agreed",
            title="D2",
            description="D2",
            decision="D2",
            agreements={"Alice": "Yes"},
        )
        decision3 = Decision(
            category="Go-to-Market",
            significance=2,
            status="Agreed",
            title="D3",
            description="D3",
            decision="D3",
            agreements={"Alice": "Yes"},
        )

        rows = decisions_to_csv_rows([decision1, decision2, decision3], ["Alice"])

        # should be sorted: GTM (sig 2), Security (sig 1), Security (sig 3)
        assert rows[1][0] == "Go-to-Market"
        assert rows[2][0] == "Security"
        assert rows[2][1] == "1"
        assert rows[3][0] == "Security"
        assert rows[3][1] == "3"

    def test_missing_participant_defaults_to_no(self) -> None:
        """Test that missing participant agreement defaults to 'No'."""
        decision = Decision(
            category="Tech",
            significance=3,
            status="Agreed",
            title="Test",
            description="Test",
            decision="Test",
            agreements={"Alice": "Yes"},
        )

        rows = decisions_to_csv_rows([decision], ["Alice", "Bob", "Carol"])

        # find agreement columns
        header = rows[0]
        alice_idx = header.index("Alice Agreed")
        bob_idx = header.index("Bob Agreed")
        carol_idx = header.index("Carol Agreed")

        data_row = rows[1]
        assert data_row[alice_idx] == "Yes"
        assert data_row[bob_idx] == "No"  # not in agreements dict
        assert data_row[carol_idx] == "No"  # not in agreements dict


class TestLoadConfig:
    """Tests for load_config function."""

    def test_load_config_nonexistent_file(self) -> None:
        """Test loading config from nonexistent file returns defaults."""
        config = load_config(Path("/nonexistent/config.yaml"))
        assert config.model == "claude-sonnet-4-20250514"
        assert len(config.participants) > 0

    def test_load_config_from_file(self, temp_config_file: Path) -> None:
        """Test loading config from YAML file."""
        config = load_config(temp_config_file)

        assert config.custom_prompt.strip().startswith("Custom instructions")
        assert len(config.participants) == 2
        assert config.participants[0].name == "Alice"
        assert config.participants[0].role == "CEO"
        assert config.participants[1].name == "Bob"
        assert len(config.categories) == 1
        assert config.categories[0].name == "Engineering"
        assert config.model == "claude-sonnet-4-20250514"
        assert config.model_provider == "anthropic"

    def test_load_config_with_string_participants(self, tmp_path: Path) -> None:
        """Test loading config with participants as simple strings."""
        yaml_content = """participants:
  - Alice
  - Bob
  - Carol
"""
        config_file = tmp_path / "simple.yaml"
        config_file.write_text(yaml_content, encoding="utf-8")

        config = load_config(config_file)
        assert len(config.participants) == 3
        assert config.participants[0].name == "Alice"
        assert config.participants[0].role == ""

    def test_load_config_empty_file(self, tmp_path: Path) -> None:
        """Test loading empty config file returns defaults."""
        config_file = tmp_path / "empty.yaml"
        config_file.write_text("", encoding="utf-8")

        config = load_config(config_file)
        assert len(config.participants) > 0  # defaults

    def test_load_config_agreement_rules(self, temp_config_file: Path) -> None:
        """Test loading agreement rules from config."""
        config = load_config(temp_config_file)

        assert "Tech" in config.agreement_rules
        tech_rule = config.agreement_rules["Tech"]
        assert tech_rule.requires_all == ["Alice", "Bob"]
        assert "CEO and CTO" in tech_rule.description


class TestSaveConfig:
    """Tests for save_config function."""

    def test_save_and_load_roundtrip(
        self,
        tmp_path: Path,
        sample_config: TrackerConfig,
    ) -> None:
        """Test saving and loading config produces equivalent result."""
        config_file = tmp_path / "roundtrip.yaml"

        save_config(sample_config, config_file)
        loaded_config = load_config(config_file)

        assert loaded_config.custom_prompt == sample_config.custom_prompt
        assert len(loaded_config.participants) == len(sample_config.participants)
        assert loaded_config.participants[0].name == sample_config.participants[0].name
        assert loaded_config.model == sample_config.model
        assert loaded_config.model_provider == sample_config.model_provider

    def test_save_config_format(self, tmp_path: Path, sample_config: TrackerConfig) -> None:
        """Test that saved config is valid YAML."""
        config_file = tmp_path / "test.yaml"
        save_config(sample_config, config_file)

        with open(config_file, encoding="utf-8") as f:
            data = yaml.safe_load(f)

        assert "custom_prompt" in data
        assert "participants" in data
        assert "model" in data
        assert data["model"] == "claude-sonnet-4-20250514"


class TestMergeFrameworks:
    """Tests for merge_frameworks function."""

    def test_merge_no_frameworks(self, sample_config: TrackerConfig) -> None:
        """Test merging with no framework files."""
        result = merge_frameworks(sample_config, [])
        assert result.custom_prompt == sample_config.custom_prompt

    def test_merge_nonexistent_framework(self, sample_config: TrackerConfig) -> None:
        """Test merging with nonexistent framework file."""
        result = merge_frameworks(sample_config, [Path("/nonexistent/framework.md")])
        assert result.custom_prompt == sample_config.custom_prompt

    def test_merge_yaml_framework(
        self,
        tmp_path: Path,
        sample_config: TrackerConfig,
    ) -> None:
        """Test merging YAML framework file."""
        framework_yaml = tmp_path / "framework.yaml"
        framework_yaml.write_text(
            """participants:
  - name: David
    role: Designer
    required_for: [Design]

custom_prompt: |
  Additional framework instructions.
""",
            encoding="utf-8",
        )

        result = merge_frameworks(sample_config, [framework_yaml])

        # participants should be replaced
        assert len(result.participants) == 1
        assert result.participants[0].name == "David"

        # custom prompt should be appended
        assert "Test custom prompt" in result.custom_prompt
        assert "Additional framework instructions" in result.custom_prompt

    def test_merge_markdown_framework(
        self,
        tmp_path: Path,
        sample_config: TrackerConfig,
    ) -> None:
        """Test merging markdown framework file."""
        framework_md = tmp_path / "framework.md"
        framework_md.write_text(
            "# Team Framework\n\nFocus on technical alignment.",
            encoding="utf-8",
        )

        result = merge_frameworks(sample_config, [framework_md])

        assert "Framework: framework.md" in result.custom_prompt
        assert "Focus on technical alignment" in result.custom_prompt

    def test_merge_multiple_frameworks(
        self,
        tmp_path: Path,
        sample_config: TrackerConfig,
    ) -> None:
        """Test merging multiple framework files in order."""
        framework1 = tmp_path / "framework1.md"
        framework1.write_text("Framework 1 content", encoding="utf-8")

        framework2 = tmp_path / "framework2.md"
        framework2.write_text("Framework 2 content", encoding="utf-8")

        result = merge_frameworks(sample_config, [framework1, framework2])

        # both should be in custom prompt
        assert "Framework 1 content" in result.custom_prompt
        assert "Framework 2 content" in result.custom_prompt

        # order should be preserved
        idx1 = result.custom_prompt.index("Framework 1")
        idx2 = result.custom_prompt.index("Framework 2")
        assert idx1 < idx2

    def test_merge_agreement_rules(
        self,
        tmp_path: Path,
        sample_config: TrackerConfig,
    ) -> None:
        """Test merging agreement rules from framework."""
        framework = tmp_path / "rules.yaml"
        framework.write_text(
            """agreement_rules:
  Design:
    requires_all: [David]
    description: Design decisions require designer approval
""",
            encoding="utf-8",
        )

        result = merge_frameworks(sample_config, [framework])

        # original rules should still exist
        assert "Tech" in result.agreement_rules

        # new rule should be added
        assert "Design" in result.agreement_rules
        assert result.agreement_rules["Design"].requires_all == ["David"]

    def test_merge_markdown_framework_with_participants(
        self,
        tmp_path: Path,
        sample_config: TrackerConfig,
    ) -> None:
        """Test that markdown framework parses participants from table."""
        framework_md = tmp_path / "framework.md"
        framework_md.write_text(
            """# Team Framework

## Participants

| Name | Role | Domain |
|------|------|--------|
| **Ryan** | CTO | Engineering |
| Ajit | CEO | Strategy |
| Milkana | PM | Product |

## Other Section

More content here.
""",
            encoding="utf-8",
        )

        result = merge_frameworks(sample_config, [framework_md])

        # participants should be extracted from markdown table
        assert len(result.participants) == 3
        names = [p.name for p in result.participants]
        assert "Ryan" in names
        assert "Ajit" in names
        assert "Milkana" in names


class TestParseMarkdownParticipants:
    """Tests for _parse_markdown_participants function."""

    def test_parse_basic_table(self) -> None:
        """Test parsing a basic participant table."""
        content = """## Participants

| Name | Role |
|------|------|
| Alice | CEO |
| Bob | CTO |
"""
        participants = _parse_markdown_participants(content)

        assert len(participants) == 2
        assert participants[0].name == "Alice"
        assert participants[0].role == "CEO"
        assert participants[1].name == "Bob"
        assert participants[1].role == "CTO"

    def test_parse_bold_names(self) -> None:
        """Test parsing names with bold markdown."""
        content = """## Participants

| Name | Role |
|------|------|
| **Ryan** | Founder |
| **Ajit** | Co-founder |
"""
        participants = _parse_markdown_participants(content)

        assert len(participants) == 2
        assert participants[0].name == "Ryan"
        assert participants[1].name == "Ajit"

    def test_stops_at_next_section(self) -> None:
        """Test that parsing stops at next ## section."""
        content = """## Participants

| Name | Role |
|------|------|
| Alice | CEO |

## Categories

| Category | Description |
|----------|-------------|
| Tech | Technical decisions |
"""
        participants = _parse_markdown_participants(content)

        assert len(participants) == 1
        assert participants[0].name == "Alice"

    def test_no_participants_section(self) -> None:
        """Test handling content without Participants section."""
        content = """## Categories

Some categories here.
"""
        participants = _parse_markdown_participants(content)

        assert len(participants) == 0

    def test_empty_table(self) -> None:
        """Test handling Participants section with only header."""
        content = """## Participants

| Name | Role |
|------|------|
"""
        participants = _parse_markdown_participants(content)

        assert len(participants) == 0


class TestGetDefaultConfig:
    """Tests for get_default_config function."""

    def test_default_config_has_participants(self) -> None:
        """Test that default config includes participants."""
        config = get_default_config()
        assert len(config.participants) > 0
        assert any(p.name == "Ryan" for p in config.participants)

    def test_default_config_has_categories(self) -> None:
        """Test that default config includes categories."""
        config = get_default_config()
        assert len(config.categories) > 0
        assert any(c.name == "Technical Architecture" for c in config.categories)

    def test_default_config_has_types(self) -> None:
        """Test that default config includes types."""
        config = get_default_config()
        assert len(config.types) > 0
        assert any(t.name == "Tech" for t in config.types)

    def test_default_config_has_agreement_rules(self) -> None:
        """Test that default config includes agreement rules."""
        config = get_default_config()
        assert len(config.agreement_rules) > 0
        assert "Tech" in config.agreement_rules


class TestTrackerConfigProperties:
    """Tests for TrackerConfig properties."""

    def test_participant_names_property(self, sample_config: TrackerConfig) -> None:
        """Test participant_names property."""
        names = sample_config.participant_names
        assert len(names) == 3
        assert "Alice" in names
        assert "Bob" in names
        assert "Carol" in names

    def test_category_names_property(self, sample_config: TrackerConfig) -> None:
        """Test category_names property."""
        names = sample_config.category_names
        assert len(names) == 2
        assert "Technical Architecture" in names
        assert "Go-to-Market" in names

    def test_type_names_property(self, sample_config: TrackerConfig) -> None:
        """Test type_names property."""
        names = sample_config.type_names
        assert len(names) == 2
        assert "Tech" in names
        assert "GTM" in names


class TestGetJSONSchemaForExtraction:
    """Tests for get_json_schema_for_extraction function."""

    def test_schema_structure(self) -> None:
        """Test basic schema structure."""
        schema = get_json_schema_for_extraction(["Alice", "Bob"])

        assert schema["type"] == "object"
        assert "decisions" in schema["properties"]
        assert schema["required"] == ["decisions"]

    def test_schema_decisions_array(self) -> None:
        """Test decisions array schema."""
        schema = get_json_schema_for_extraction(["Alice", "Bob"])
        decisions = schema["properties"]["decisions"]

        assert decisions["type"] == "array"
        assert "items" in decisions

    def test_schema_decision_properties(self) -> None:
        """Test decision item properties."""
        schema = get_json_schema_for_extraction(["Alice", "Bob"])
        decision_item = schema["properties"]["decisions"]["items"]

        assert "category" in decision_item["properties"]
        assert "significance" in decision_item["properties"]
        assert "status" in decision_item["properties"]
        assert "agreements" in decision_item["properties"]

    def test_schema_significance_constraints(self) -> None:
        """Test significance field constraints."""
        schema = get_json_schema_for_extraction(["Alice"])
        significance = schema["properties"]["decisions"]["items"]["properties"]["significance"]

        assert significance["type"] == "integer"
        assert significance["minimum"] == 1
        assert significance["maximum"] == 5

    def test_schema_status_enum(self) -> None:
        """Test status field enum values."""
        schema = get_json_schema_for_extraction(["Alice"])
        status = schema["properties"]["decisions"]["items"]["properties"]["status"]

        assert status["type"] == "string"
        assert "Agreed" in status["enum"]
        assert "Needs Clarification" in status["enum"]
        assert "Unresolved" in status["enum"]

    def test_schema_dynamic_participants(self) -> None:
        """Test that agreements schema includes all participants."""
        participants = ["Alice", "Bob", "Carol"]
        schema = get_json_schema_for_extraction(participants)
        agreements = schema["properties"]["decisions"]["items"]["properties"]["agreements"]

        assert agreements["type"] == "object"
        assert set(agreements["properties"].keys()) == set(participants)
        assert agreements["required"] == participants

        # check each participant has correct enum
        for name in participants:
            participant_schema = agreements["properties"][name]
            assert participant_schema["type"] == "string"
            assert set(participant_schema["enum"]) == {"Yes", "Partial", "No", "Not Present"}


@pytest.mark.skip(reason="build_json_extraction_prompt now uses external prompt templates")
class TestBuildJSONExtractionPrompt:
    """Tests for build_json_extraction_prompt function.

    Note: These tests are skipped because the function now loads prompts from external
    template files. The prompt structure is tested indirectly through integration tests.
    """

    def test_prompt_includes_participants(
        self,
        sample_config: TrackerConfig,
        sample_transcript: str,
    ) -> None:
        """Test that prompt includes participant names."""
        pass

    def test_prompt_includes_categories(
        self,
        sample_config: TrackerConfig,
        sample_transcript: str,
    ) -> None:
        """Test that prompt includes categories."""
        pass

    def test_prompt_includes_types(
        self,
        sample_config: TrackerConfig,
        sample_transcript: str,
    ) -> None:
        """Test that prompt includes types."""
        pass

    def test_prompt_includes_agreement_rules(
        self,
        sample_config: TrackerConfig,
        sample_transcript: str,
    ) -> None:
        """Test that prompt includes agreement rules."""
        pass

    def test_prompt_includes_custom_instructions(
        self,
        sample_config: TrackerConfig,
        sample_transcript: str,
    ) -> None:
        """Test that prompt includes custom instructions."""
        pass

    def test_prompt_includes_transcript(
        self,
        sample_config: TrackerConfig,
        sample_transcript: str,
    ) -> None:
        """Test that prompt includes the transcript."""
        pass

    def test_prompt_structure(
        self,
        sample_config: TrackerConfig,
        sample_transcript: str,
    ) -> None:
        """Test overall prompt structure."""
        pass

    def test_prompt_example_json(
        self,
        sample_config: TrackerConfig,
        sample_transcript: str,
    ) -> None:
        """Test that prompt includes example JSON with participant names."""
        pass
