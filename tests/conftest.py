"""Common fixtures and test configuration for groundtruth tests."""

from pathlib import Path
from typing import Any

import pytest

from groundtruth.config import (
    AgreementRule,
    CategoryConfig,
    Decision,
    ParticipantConfig,
    TrackerConfig,
    TypeConfig,
)


@pytest.fixture
def sample_decision_data() -> dict[str, Any]:
    """Sample valid decision data for testing."""
    return {
        "category": "Technical Architecture",
        "significance": 2,
        "status": "Agreed",
        "title": "Use PostgreSQL for data storage",
        "description": "Team decided to use PostgreSQL as the primary database",
        "decision": "PostgreSQL will be used for all persistent data storage",
        "agreements": {
            "Alice": "Yes",
            "Bob": "Yes",
            "Carol": "Partial",
        },
        "notes": "Discussed performance vs complexity tradeoffs",
        "meeting_date": "2025-01-15",
        "meeting_reference": "team-sync-2025-01-15.txt",
    }


@pytest.fixture
def sample_decision(sample_decision_data: dict[str, Any]) -> Decision:
    """Sample Decision object."""
    return Decision(**sample_decision_data)


@pytest.fixture
def sample_participants() -> list[ParticipantConfig]:
    """Sample participant configurations."""
    return [
        ParticipantConfig(name="Alice", role="CEO", required_for=["Strategy"]),
        ParticipantConfig(name="Bob", role="CTO", required_for=["Tech"]),
        ParticipantConfig(name="Carol", role="Product Manager", required_for=["GTM"]),
    ]


@pytest.fixture
def sample_categories() -> list[CategoryConfig]:
    """Sample category configurations."""
    return [
        CategoryConfig(
            name="Technical Architecture",
            description="System design and technical decisions",
            examples=["database choice", "API design"],
        ),
        CategoryConfig(
            name="Go-to-Market",
            description="Launch and marketing strategy",
            examples=["pricing", "launch timing"],
        ),
    ]


@pytest.fixture
def sample_types() -> list[TypeConfig]:
    """Sample type configurations."""
    return [
        TypeConfig(name="Tech", description="Technical implementation"),
        TypeConfig(name="GTM", description="Go-to-market strategy"),
    ]


@pytest.fixture
def sample_agreement_rules() -> dict[str, AgreementRule]:
    """Sample agreement rules."""
    return {
        "Tech": AgreementRule(
            requires_all=["Alice", "Bob"],
            description="Tech decisions require CEO and CTO",
        ),
        "GTM": AgreementRule(
            requires_any=["Alice", "Carol"],
            description="GTM decisions require CEO or PM",
        ),
    }


@pytest.fixture
def sample_config(
    sample_participants: list[ParticipantConfig],
    sample_categories: list[CategoryConfig],
    sample_types: list[TypeConfig],
    sample_agreement_rules: dict[str, AgreementRule],
) -> TrackerConfig:
    """Sample tracker configuration."""
    return TrackerConfig(
        custom_prompt="Test custom prompt",
        participants=sample_participants,
        categories=sample_categories,
        types=sample_types,
        agreement_rules=sample_agreement_rules,
        model="claude-sonnet-4-20250514",
        model_provider="claude-code",
        default_output_format="xlsx",
    )


@pytest.fixture
def sample_transcript() -> str:
    """Sample meeting transcript for testing."""
    return """Meeting Transcript - 2025-01-15

Alice: Let's discuss the database choice for our new platform.

Bob: I've evaluated several options. PostgreSQL seems like the best fit given our needs
for ACID compliance and strong ecosystem support.

Carol: How does this affect our timeline? Will it delay the launch?

Bob: No delays. PostgreSQL is well-supported and our team has experience with it.

Alice: I agree with Bob's recommendation. Let's move forward with PostgreSQL.

Carol: Sounds good. I'm partially on board - I trust the technical decision but want to
revisit performance benchmarks before we launch.

Alice: That's fair. Let's mark this as decided and schedule performance testing.

Bob: Agreed. I'll set up the initial schema this week.
"""


@pytest.fixture
def sample_yaml_config() -> str:
    """Sample YAML configuration content."""
    return """custom_prompt: |
  Custom instructions for decision extraction.
  Focus on technical alignment.

participants:
  - name: Alice
    role: CEO
    required_for: [Strategy, GTM]
  - name: Bob
    role: CTO
    required_for: [Tech]

categories:
  - name: Engineering
    description: Technical implementation decisions
    examples: [database, architecture]

types:
  - name: Tech
    description: Technical decisions

agreement_rules:
  Tech:
    requires_all: [Alice, Bob]
    description: Tech decisions require both CEO and CTO

model: claude-sonnet-4-20250514
model_provider: anthropic
default_output_format: xlsx
"""


@pytest.fixture
def temp_transcript_file(tmp_path: Path, sample_transcript: str) -> Path:
    """Create a temporary transcript file."""
    transcript_file = tmp_path / "meeting-2025-01-15.txt"
    transcript_file.write_text(sample_transcript, encoding="utf-8")
    return transcript_file


@pytest.fixture
def temp_config_file(tmp_path: Path, sample_yaml_config: str) -> Path:
    """Create a temporary config file."""
    config_file = tmp_path / "config.yaml"
    config_file.write_text(sample_yaml_config, encoding="utf-8")
    return config_file


@pytest.fixture
def sample_json_response() -> str:
    """Sample JSON response from LLM extraction."""
    return """{
  "decisions": [
    {
      "category": "Technical Architecture",
      "significance": 2,
      "status": "Agreed",
      "title": "Use PostgreSQL for data storage",
      "description": "Team decided to use PostgreSQL as the primary database",
      "decision": "PostgreSQL will be used for all persistent data storage",
      "agreements": {
        "Alice": "Yes",
        "Bob": "Yes",
        "Carol": "Partial"
      },
      "notes": "Discussed performance vs complexity tradeoffs",
      "meeting_date": "2025-01-15",
      "meeting_reference": "meeting-2025-01-15.txt"
    }
  ]
}"""


@pytest.fixture
def sample_json_response_with_markdown() -> str:
    """Sample JSON response wrapped in markdown code blocks."""
    return """```json
{
  "decisions": [
    {
      "category": "Technical Architecture",
      "significance": 2,
      "status": "Agreed",
      "title": "Use PostgreSQL for data storage",
      "description": "Team decided to use PostgreSQL as the primary database",
      "decision": "PostgreSQL will be used for all persistent data storage",
      "agreements": {
        "Alice": "Yes",
        "Bob": "Yes",
        "Carol": "Partial"
      },
      "notes": "Discussed performance vs complexity tradeoffs",
      "meeting_date": "2025-01-15",
      "meeting_reference": "meeting-2025-01-15.txt"
    }
  ]
}
```"""


@pytest.fixture
def sample_participant_detection_response() -> str:
    """Sample participant detection JSON response."""
    return """{
  "participants": [
    {"name": "Alice", "role": "CEO"},
    {"name": "Bob", "role": "CTO"},
    {"name": "Carol", "role": "Product Manager"}
  ],
  "reasoning": "Identified three active participants based on dialogue attribution"
}"""
