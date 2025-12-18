"""Tests for groundtruth.llm module."""

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, Mock, patch

import pytest

from groundtruth.config import (
    Decision,
    ExtractionResult,
    ParticipantConfig,
    TrackerConfig,
)
from groundtruth.llm import (
    ClaudeCodeProvider,
    EmptyResponseError,
    LiteLLMProvider,
    Metrics,
    extract_decisions_from_transcript_json,
    get_provider,
    validate_decision,
)


class TestMetrics:
    """Tests for Metrics class."""

    def test_metrics_initialization(self) -> None:
        """Test metrics initializes with zero values."""
        metrics = Metrics()
        assert metrics.llm_calls == 0
        assert metrics.files_processed == 0
        assert metrics.participant_detection_time == 0.0
        assert metrics.decision_extraction_time == 0.0

    def test_metrics_reset(self) -> None:
        """Test metrics reset functionality."""
        metrics = Metrics()
        metrics.llm_calls = 5
        metrics.files_processed = 3
        metrics.participant_detection_time = 10.5

        metrics.reset()

        assert metrics.llm_calls == 0
        assert metrics.files_processed == 0
        assert metrics.participant_detection_time == 0.0

    def test_metrics_log_summary(self, caplog: pytest.LogCaptureFixture) -> None:
        """Test that log_summary outputs metrics."""
        metrics = Metrics()
        metrics.files_processed = 2
        metrics.llm_calls = 4
        metrics.participant_detection_time = 5.0
        metrics.decision_extraction_time = 10.0

        with caplog.at_level("INFO"):
            metrics.log_summary()

        # check that summary was logged
        assert "PERFORMANCE METRICS" in caplog.text
        assert "files=2" in caplog.text
        assert "llm_calls=4" in caplog.text


class TestLiteLLMProvider:
    """Tests for LiteLLMProvider class."""

    def test_initialization_default_model(self) -> None:
        """Test LiteLLMProvider initializes with default model."""
        provider = LiteLLMProvider()
        assert provider.model == "claude-sonnet-4-20250514"

    def test_initialization_custom_model(self) -> None:
        """Test LiteLLMProvider initializes with custom model."""
        provider = LiteLLMProvider(model="gpt-4")
        assert provider.model == "gpt-4"


class TestClaudeCodeProvider:
    """Tests for ClaudeCodeProvider class."""

    def test_initialization_default_path(self) -> None:
        """Test ClaudeCodeProvider initializes with default CLI path."""
        provider = ClaudeCodeProvider()
        assert provider.claude_code_path == "claude"

    def test_initialization_custom_path(self) -> None:
        """Test ClaudeCodeProvider initializes with custom CLI path."""
        provider = ClaudeCodeProvider(claude_code_path="/usr/local/bin/claude")
        assert provider.claude_code_path == "/usr/local/bin/claude"

    def test_parse_json_extraction_response_envelope_with_string(self) -> None:
        """Test parsing JSON extraction response with envelope wrapper."""
        provider = ClaudeCodeProvider()
        envelope_response = """{
  "result": "{\\"decisions\\": [{\\"category\\": \\"Tech\\", \\"significance\\": 2, \\"status\\": \\"Agreed\\", \\"title\\": \\"Test\\", \\"description\\": \\"Test\\", \\"decision\\": \\"Test\\", \\"agreements\\": {\\"Alice\\": \\"Yes\\"}}]}"
}"""

        result = provider._parse_json_extraction_response(
            envelope_response,
            ["Alice"],
        )

        assert len(result.decisions) == 1
        assert result.decisions[0].category == "Tech"

    def test_parse_json_extraction_response_envelope_with_dict(self) -> None:
        """Test parsing JSON extraction response with dict result."""
        provider = ClaudeCodeProvider()
        envelope_response = """{
  "result": {
    "decisions": [
      {
        "category": "Tech",
        "significance": 2,
        "status": "Agreed",
        "title": "Test",
        "description": "Test",
        "decision": "Test",
        "agreements": {"Alice": "Yes"}
      }
    ]
  }
}"""

        result = provider._parse_json_extraction_response(
            envelope_response,
            ["Alice"],
        )

        assert len(result.decisions) == 1
        assert result.decisions[0].category == "Tech"

    def test_parse_json_extraction_response_direct_json(self) -> None:
        """Test parsing direct JSON response without envelope."""
        provider = ClaudeCodeProvider()
        direct_response = """{
  "decisions": [
    {
      "category": "Tech",
      "significance": 2,
      "status": "Agreed",
      "title": "Test",
      "description": "Test",
      "decision": "Test",
      "agreements": {"Alice": "Yes"}
    }
  ]
}"""

        result = provider._parse_json_extraction_response(direct_response, ["Alice"])

        assert len(result.decisions) == 1
        assert result.decisions[0].title == "Test"

    def test_parse_json_extraction_response_with_markdown(self) -> None:
        """Test parsing JSON with markdown code blocks in envelope."""
        provider = ClaudeCodeProvider()
        envelope_response = """{
  "result": "```json\\n{\\"decisions\\": []}\\n```"
}"""

        result = provider._parse_json_extraction_response(envelope_response, [])
        assert len(result.decisions) == 0

    def test_parse_json_extraction_response_invalid_decision(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test that invalid decisions are skipped with warning."""
        provider = ClaudeCodeProvider()
        response = """{
  "decisions": [
    {
      "category": "Tech",
      "significance": 99,
      "status": "Agreed",
      "title": "Test",
      "description": "Test",
      "decision": "Test",
      "agreements": {"Alice": "Yes"}
    }
  ]
}"""

        with caplog.at_level("WARNING"):
            result = provider._parse_json_extraction_response(response, ["Alice"])

        assert len(result.decisions) == 0
        assert "Failed to parse decision" in caplog.text

    def test_parse_json_extraction_response_invalid_json(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test handling of invalid JSON in extraction response."""
        provider = ClaudeCodeProvider()
        invalid_response = "This is not JSON"

        with caplog.at_level("ERROR"):
            result = provider._parse_json_extraction_response(invalid_response, [])

        assert len(result.decisions) == 0
        assert "Failed to parse JSON response" in caplog.text

    @patch("groundtruth.config.get_decision_extraction_prompt")
    @patch("groundtruth.llm.subprocess.run")
    def test_extract_decisions_json_success(
        self,
        mock_run: Mock,
        mock_get_prompt: Mock,
        sample_config: TrackerConfig,
    ) -> None:
        """Test successful JSON decision extraction."""
        provider = ClaudeCodeProvider()
        mock_get_prompt.return_value = "Extract decisions from: {transcript}"

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = """{
  "result": {
    "decisions": [
      {
        "category": "Tech",
        "significance": 2,
        "status": "Agreed",
        "title": "Test Decision",
        "description": "Test",
        "decision": "Test",
        "agreements": {"Alice": "Yes", "Bob": "Yes", "Carol": "No"}
      }
    ]
  }
}"""
        mock_run.return_value = mock_result

        result = provider.extract_decisions_json("Test transcript", sample_config)

        assert len(result.decisions) == 1
        assert result.decisions[0].title == "Test Decision"

        # verify CLI was called with correct arguments
        mock_run.assert_called_once()
        call_args = mock_run.call_args
        assert "--output-format" in call_args.args[0]
        assert "json" in call_args.args[0]

    @patch("groundtruth.llm.time.sleep")
    @patch("groundtruth.config.get_decision_extraction_prompt")
    @patch("groundtruth.llm.subprocess.run")
    def test_extract_decisions_json_cli_error(
        self,
        mock_run: Mock,
        mock_get_prompt: Mock,
        mock_sleep: Mock,
        sample_config: TrackerConfig,
    ) -> None:
        """Test handling of CLI error in decision extraction with retry."""
        provider = ClaudeCodeProvider()
        mock_get_prompt.return_value = "Extract decisions from: {transcript}"

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "CLI error"
        mock_run.return_value = mock_result

        # should raise EmptyResponseError after all retries fail
        with pytest.raises(EmptyResponseError, match="CLI failed"):
            provider.extract_decisions_json("Test", sample_config)

        # verify retries happened (4 total calls: 1 initial + 3 retries)
        assert mock_run.call_count == 4

    @patch("groundtruth.llm.time.sleep")
    @patch("groundtruth.config.get_decision_extraction_prompt")
    @patch("groundtruth.llm.subprocess.run")
    def test_extract_decisions_json_timeout(
        self,
        mock_run: Mock,
        mock_get_prompt: Mock,
        mock_sleep: Mock,
        sample_config: TrackerConfig,
    ) -> None:
        """Test handling of timeout in decision extraction with retry."""
        provider = ClaudeCodeProvider()
        mock_get_prompt.return_value = "Extract decisions from: {transcript}"
        mock_run.side_effect = subprocess.TimeoutExpired("claude", 300)

        # should raise TimeoutExpired after all retries fail
        with pytest.raises(subprocess.TimeoutExpired):
            provider.extract_decisions_json("Test", sample_config)

        # verify retries happened
        assert mock_run.call_count == 4

    @patch("groundtruth.config.get_decision_extraction_prompt")
    @patch("groundtruth.llm.subprocess.run")
    def test_extract_decisions_json_not_found(
        self,
        mock_run: Mock,
        mock_get_prompt: Mock,
        sample_config: TrackerConfig,
    ) -> None:
        """Test handling of CLI not found error."""
        provider = ClaudeCodeProvider()
        mock_get_prompt.return_value = "Extract decisions from: {transcript}"
        mock_run.side_effect = FileNotFoundError()

        with pytest.raises(RuntimeError, match="not found"):
            provider.extract_decisions_json("Test", sample_config)


class TestGetProvider:
    """Tests for get_provider function."""

    def test_get_claude_code_provider(self, sample_config: TrackerConfig) -> None:
        """Test getting Claude Code provider."""
        sample_config.model_provider = "claude-code"
        provider = get_provider(sample_config)

        assert isinstance(provider, ClaudeCodeProvider)

    def test_get_claude_code_provider_case_insensitive(
        self,
        sample_config: TrackerConfig,
    ) -> None:
        """Test that provider type is case insensitive."""
        sample_config.model_provider = "CLAUDE-CODE"
        provider = get_provider(sample_config)

        assert isinstance(provider, ClaudeCodeProvider)

    def test_get_litellm_provider_anthropic(
        self,
        sample_config: TrackerConfig,
    ) -> None:
        """Test getting LiteLLM provider for Anthropic."""
        sample_config.model_provider = "anthropic"
        sample_config.model = "claude-sonnet-4-20250514"
        provider = get_provider(sample_config)

        assert isinstance(provider, LiteLLMProvider)
        assert provider.model == "claude-sonnet-4-20250514"

    def test_get_litellm_provider_openai(self, sample_config: TrackerConfig) -> None:
        """Test getting LiteLLM provider for OpenAI."""
        sample_config.model_provider = "openai"
        sample_config.model = "gpt-4"
        provider = get_provider(sample_config)

        assert isinstance(provider, LiteLLMProvider)
        assert provider.model == "gpt-4"


class TestExtractDecisionsFromTranscriptJSON:
    """Tests for extract_decisions_from_transcript_json function."""

    @patch("groundtruth.llm.get_provider")
    def test_extract_decisions_success(
        self,
        mock_get_provider: Mock,
        temp_transcript_file: Path,
        sample_config: TrackerConfig,
    ) -> None:
        """Test successful decision extraction from file."""
        mock_provider = MagicMock()
        mock_provider.extract_decisions_json.return_value = ExtractionResult(
            decisions=[
                Decision(
                    category="Tech",
                    significance=2,
                    status="Agreed",
                    title="Test",
                    description="Test",
                    decision="Test",
                    agreements={"Alice": "Yes"},
                )
            ],
            participants_detected=["Alice"],
        )
        mock_get_provider.return_value = mock_provider

        result = extract_decisions_from_transcript_json(
            temp_transcript_file,
            sample_config,
        )

        assert len(result.decisions) == 1
        assert result.decisions[0].meeting_reference == "meeting-2025-01-15.txt"

    @patch("groundtruth.llm.get_provider")
    def test_extract_decisions_extracts_date_from_filename(
        self,
        mock_get_provider: Mock,
        temp_transcript_file: Path,
        sample_config: TrackerConfig,
    ) -> None:
        """Test that meeting date is extracted from filename."""
        mock_provider = MagicMock()
        mock_provider.extract_decisions_json.return_value = ExtractionResult(
            decisions=[
                Decision(
                    category="Tech",
                    significance=2,
                    status="Agreed",
                    title="Test",
                    description="Test",
                    decision="Test",
                    agreements={"Alice": "Yes"},
                )
            ],
        )
        mock_get_provider.return_value = mock_provider

        result = extract_decisions_from_transcript_json(
            temp_transcript_file,
            sample_config,
        )

        assert result.decisions[0].meeting_date == "2025-01-15"

    @patch("groundtruth.llm.get_provider")
    def test_extract_decisions_provider_not_supported(
        self,
        mock_get_provider: Mock,
        temp_transcript_file: Path,
        sample_config: TrackerConfig,
    ) -> None:
        """Test error when provider doesn't support JSON extraction."""
        # mock provider without extract_decisions_json method
        mock_provider = MagicMock(spec=LiteLLMProvider)
        mock_get_provider.return_value = mock_provider

        with pytest.raises(NotImplementedError, match="does not support JSON extraction"):
            extract_decisions_from_transcript_json(
                temp_transcript_file,
                sample_config,
            )

    @patch("groundtruth.llm.get_provider")
    def test_extract_decisions_fills_meeting_metadata(
        self,
        mock_get_provider: Mock,
        temp_transcript_file: Path,
        sample_config: TrackerConfig,
    ) -> None:
        """Test that meeting date and reference are filled in."""
        mock_provider = MagicMock()
        mock_provider.extract_decisions_json.return_value = ExtractionResult(
            decisions=[
                Decision(
                    category="Tech",
                    significance=2,
                    status="Agreed",
                    title="Test",
                    description="Test",
                    decision="Test",
                    agreements={"Alice": "Yes"},
                    meeting_date="",
                    meeting_reference="",
                )
            ],
        )
        mock_get_provider.return_value = mock_provider

        result = extract_decisions_from_transcript_json(
            temp_transcript_file,
            sample_config,
            meeting_date="2025-02-20",
        )

        assert result.decisions[0].meeting_date == "2025-02-20"
        assert result.decisions[0].meeting_reference == "meeting-2025-01-15.txt"


class TestValidateDecision:
    """Tests for validate_decision function."""

    def test_all_yes_status_agreed_unchanged(self) -> None:
        """Test that Status='Agreed' with all 'Yes' is unchanged."""
        decision = Decision(
            category="Tech",
            significance=3,
            status="Agreed",
            title="Test Decision",
            description="Test",
            decision="Test",
            agreements={"Alice": "Yes", "Bob": "Yes", "Carol": "Yes"},
        )

        result = validate_decision(decision)

        assert result.status == "Agreed"

    def test_agreed_with_partial_corrected(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test that Status='Agreed' with 'Partial' is corrected to 'Needs Clarification'."""
        decision = Decision(
            category="Tech",
            significance=3,
            status="Agreed",
            title="Test Decision",
            description="Test",
            decision="Test",
            agreements={"Alice": "Yes", "Bob": "Partial"},
        )

        with caplog.at_level("WARNING"):
            result = validate_decision(decision)

        assert result.status == "Needs Clarification"
        assert "Fixed status inconsistency" in caplog.text
        assert "'Agreed' to 'Needs Clarification'" in caplog.text

    def test_agreed_with_no_corrected(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test that Status='Agreed' with 'No' is corrected to 'Unresolved'."""
        decision = Decision(
            category="Tech",
            significance=3,
            status="Agreed",
            title="Test Decision",
            description="Test",
            decision="Test",
            agreements={"Alice": "Yes", "Bob": "No"},
        )

        with caplog.at_level("WARNING"):
            result = validate_decision(decision)

        assert result.status == "Unresolved"
        assert "Fixed status inconsistency" in caplog.text

    def test_unresolved_with_all_yes_corrected(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test that Status='Unresolved' with all 'Yes' is corrected to 'Agreed'."""
        decision = Decision(
            category="Tech",
            significance=3,
            status="Unresolved",
            title="Test Decision",
            description="Test",
            decision="Test",
            agreements={"Alice": "Yes", "Bob": "Yes"},
        )

        with caplog.at_level("WARNING"):
            result = validate_decision(decision)

        assert result.status == "Agreed"
        assert "Fixed status inconsistency" in caplog.text

    def test_needs_clarification_with_partial_unchanged(self) -> None:
        """Test that Status='Needs Clarification' with 'Partial' is unchanged."""
        decision = Decision(
            category="Tech",
            significance=3,
            status="Needs Clarification",
            title="Test Decision",
            description="Test",
            decision="Test",
            agreements={"Alice": "Yes", "Bob": "Partial"},
        )

        result = validate_decision(decision)

        assert result.status == "Needs Clarification"

    def test_no_overrides_partial(self) -> None:
        """Test that 'No' takes precedence over 'Partial'."""
        decision = Decision(
            category="Tech",
            significance=3,
            status="Needs Clarification",
            title="Test Decision",
            description="Test",
            decision="Test",
            agreements={"Alice": "Partial", "Bob": "No"},
        )

        result = validate_decision(decision)

        assert result.status == "Unresolved"

    def test_empty_agreements_unchanged(self) -> None:
        """Test that decisions with empty agreements are unchanged."""
        decision = Decision(
            category="Tech",
            significance=3,
            status="Agreed",
            title="Test Decision",
            description="Test",
            decision="Test",
            agreements={},
        )

        result = validate_decision(decision)

        assert result.status == "Agreed"

    def test_single_participant_yes(self) -> None:
        """Test single participant with 'Yes' is 'Agreed'."""
        decision = Decision(
            category="Tech",
            significance=3,
            status="Needs Clarification",
            title="Test Decision",
            description="Test",
            decision="Test",
            agreements={"Alice": "Yes"},
        )

        result = validate_decision(decision)

        assert result.status == "Agreed"

    def test_single_participant_no(self) -> None:
        """Test single participant with 'No' is 'Unresolved'."""
        decision = Decision(
            category="Tech",
            significance=3,
            status="Agreed",
            title="Test Decision",
            description="Test",
            decision="Test",
            agreements={"Alice": "No"},
        )

        result = validate_decision(decision)

        assert result.status == "Unresolved"

    def test_not_present_excluded_from_status(self) -> None:
        """Test that 'Not Present' is excluded from status calculation."""
        decision = Decision(
            category="Tech",
            significance=3,
            status="Needs Clarification",
            title="Test Decision",
            description="Test",
            decision="Test",
            agreements={"Alice": "Yes", "Bob": "Yes", "Carol": "Not Present"},
        )

        result = validate_decision(decision)

        # all PRESENT participants said Yes, so should be Agreed
        assert result.status == "Agreed"

    def test_not_present_with_partial(self) -> None:
        """Test 'Not Present' with 'Partial' from present person."""
        decision = Decision(
            category="Tech",
            significance=3,
            status="Agreed",
            title="Test Decision",
            description="Test",
            decision="Test",
            agreements={"Alice": "Yes", "Bob": "Partial", "Carol": "Not Present"},
        )

        result = validate_decision(decision)

        # Bob is Partial, so should be Needs Clarification
        assert result.status == "Needs Clarification"

    def test_all_not_present_unchanged(self) -> None:
        """Test that all 'Not Present' leaves status unchanged."""
        decision = Decision(
            category="Tech",
            significance=3,
            status="Agreed",
            title="Test Decision",
            description="Test",
            decision="Test",
            agreements={"Alice": "Not Present", "Bob": "Not Present"},
        )

        result = validate_decision(decision)

        # no present participants, status unchanged
        assert result.status == "Agreed"
