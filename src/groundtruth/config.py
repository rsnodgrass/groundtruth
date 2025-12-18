"""Configuration management for Groundtruth with customizable prompts."""

from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

import yaml
from pydantic import BaseModel, Field

from groundtruth.prompts import get_decision_extraction_prompt

if TYPE_CHECKING:
    from groundtruth.config import ParticipantConfig


# JSON intermediate format models
class Decision(BaseModel):
    """A single extracted decision."""

    category: str = Field(description="Decision category (e.g., Technical Architecture, GTM)")
    significance: int = Field(ge=1, le=5, description="1=Critical, 5=Minor")
    status: Literal["Agreed", "Needs Clarification", "Unresolved"] = Field(
        description="Agreement status"
    )
    title: str = Field(description="Short descriptive title (3-8 words)")
    description: str = Field(description="Full context about the decision")
    decision: str = Field(description="What was decided, or 'No decision reached'")
    agreements: dict[str, Literal["Yes", "Partial", "No", "Not Present"]] = Field(
        description="Per-person agreement status"
    )
    notes: str = Field(default="", description="Supporting evidence from transcript")
    meeting_date: str = Field(default="", description="YYYY-MM-DD format")
    meeting_reference: str = Field(default="", description="Source transcript filename")


class ExtractionResult(BaseModel):
    """Result of extracting decisions from a transcript."""

    decisions: list[Decision] = Field(description="List of extracted decisions")
    participants_detected: list[str] = Field(
        default_factory=list, description="Participants found in transcript"
    )


class ExtractionMetadata(BaseModel):
    """Metadata about the extraction process."""

    transcript_path: str = ""
    transcript_chars: int = 0
    extraction_time_ms: int = 0
    participant_detection_time_ms: int = 0
    model: str = ""
    provider: str = ""


class FileExtractionResult(BaseModel):
    """Complete result for a single file extraction."""

    result: ExtractionResult
    metadata: ExtractionMetadata


def get_json_schema_for_extraction(participant_names: list[str]) -> dict:
    """
    Generate JSON schema for decision extraction.

    The schema is dynamic based on participant names.
    """
    return {
        "type": "object",
        "properties": {
            "decisions": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "category": {"type": "string"},
                        "significance": {"type": "integer", "minimum": 1, "maximum": 5},
                        "status": {"type": "string", "enum": ["Agreed", "Needs Clarification", "Unresolved"]},
                        "title": {"type": "string"},
                        "description": {"type": "string"},
                        "decision": {"type": "string"},
                        "agreements": {
                            "type": "object",
                            "properties": {name: {"type": "string", "enum": ["Yes", "Partial", "No", "Not Present"]} for name in participant_names},
                            "required": participant_names,
                        },
                        "notes": {"type": "string"},
                        "meeting_date": {"type": "string"},
                        "meeting_reference": {"type": "string"},
                    },
                    "required": ["category", "significance", "status", "title", "description", "decision", "agreements"],
                },
            },
        },
        "required": ["decisions"],
    }


def decisions_to_csv_rows(
    decisions: list[Decision],
    participant_names: list[str],
) -> list[list[str]]:
    """
    Convert Decision objects to CSV rows.

    Args:
        decisions: List of Decision objects
        participant_names: Ordered list of participant names for agreement columns

    Returns:
        List of CSV rows including header
    """
    # build header
    agreed_cols = [f"{name} Agreed" for name in participant_names]
    header = ["Category", "Significance", "Status", "Title", "Description", "Decision"] + agreed_cols + ["Notes", "Meeting Date", "Meeting Reference"]

    rows = [header]

    # sort by category then significance
    sorted_decisions = sorted(decisions, key=lambda d: (d.category, d.significance))

    for d in sorted_decisions:
        # build agreement values in order
        agreement_values = [d.agreements.get(name, "No") for name in participant_names]

        row = [
            d.category,
            str(d.significance),
            d.status,
            d.title,
            d.description,
            d.decision,
            *agreement_values,
            d.notes,
            d.meeting_date,
            d.meeting_reference,
        ]
        rows.append(row)

    return rows


class AgreementRule(BaseModel):
    """Agreement rule for a decision type or category."""

    requires_all: list[str] = []  # all these participants must agree
    requires_any: list[str] = []  # at least one of these must agree
    description: str = ""


class CategoryConfig(BaseModel):
    """Configuration for a decision category."""

    name: str
    description: str = ""
    examples: list[str] = []


class TypeConfig(BaseModel):
    """Configuration for a decision type."""

    name: str
    description: str = ""


class ParticipantConfig(BaseModel):
    """Configuration for a meeting participant."""

    name: str
    role: str = ""
    required_for: list[str] = []  # types/categories requiring this person's agreement


class TrackerConfig(BaseModel):
    """Full configuration for Groundtruth customization."""

    # custom prompt that overrides or extends default behavior
    custom_prompt: str = ""

    # participants
    participants: list[ParticipantConfig] = []

    # flag to indicate participants were explicitly set from framework/config
    # (prevents auto-detection from overriding them)
    participants_from_framework: bool = False

    # categories (if empty, uses defaults)
    categories: list[CategoryConfig] = []

    # types (if empty, uses defaults)
    types: list[TypeConfig] = []

    # agreement rules by type or category
    agreement_rules: dict[str, AgreementRule] = {}

    # model configuration
    model: str = "claude-sonnet-4-20250514"
    model_provider: str = "claude-code"  # claude-code (default), anthropic, openai, etc.

    # output preferences
    default_output_format: str = "xlsx"  # xlsx or csv

    @property
    def participant_names(self) -> list[str]:
        """Get list of participant names."""
        return [p.name for p in self.participants]

    @property
    def category_names(self) -> list[str]:
        """Get list of category names."""
        return [c.name for c in self.categories]

    @property
    def type_names(self) -> list[str]:
        """Get list of type names."""
        return [t.name for t in self.types]


# default categories
DEFAULT_CATEGORIES = [
    CategoryConfig(
        name="Go-to-Market",
        description="Launch strategy, open source, GitHub stars, market positioning, pricing",
        examples=["launch timing", "pricing model", "target market"],
    ),
    CategoryConfig(
        name="Product Tiers",
        description="Offline/single-player/multiplayer/enterprise modes, login, feature gating",
        examples=["free vs paid features", "access levels"],
    ),
    CategoryConfig(
        name="Technical Architecture",
        description="Caching, data flow, server vs client, API design, system design",
        examples=["database choice", "API structure", "caching strategy"],
    ),
    CategoryConfig(
        name="Data & Privacy",
        description="Telemetry, privacy levels, what data is collected/shared, retention",
        examples=["data collection", "privacy settings", "data retention"],
    ),
    CategoryConfig(
        name="Security",
        description="Authentication, authorization, UUID model, access control, secrets",
        examples=["auth method", "access control", "secret management"],
    ),
    CategoryConfig(
        name="Terminology",
        description="Naming conventions, taxonomy definitions, vocabulary alignment",
        examples=["naming standards", "term definitions"],
    ),
    CategoryConfig(
        name="Process",
        description="Development workflow, deployment, team coordination, meetings",
        examples=["release process", "code review", "meeting cadence"],
    ),
]

DEFAULT_TYPES = [
    TypeConfig(name="Tech", description="Technical implementation, architecture, tooling"),
    TypeConfig(name="Legal", description="Contracts, liability, terms of service, IP"),
    TypeConfig(name="Compliance", description="SOC 2, HIPAA, GDPR, regulatory requirements"),
    TypeConfig(name="GTM", description="Go-to-market, launch, distribution, partnerships"),
    TypeConfig(name="Strategy", description="Company direction, positioning, competitive"),
    TypeConfig(name="Marketing", description="Messaging, branding, content, campaigns"),
]

DEFAULT_PARTICIPANTS = [
    ParticipantConfig(name="Ryan", role="CTO", required_for=["Tech"]),
    ParticipantConfig(name="Ajit", role="CEO", required_for=["Tech", "Strategy"]),
    ParticipantConfig(name="Milkana", role="Product Manager", required_for=["GTM", "Marketing"]),
]


def get_default_config() -> TrackerConfig:
    """Get the default configuration."""
    return TrackerConfig(
        participants=DEFAULT_PARTICIPANTS,
        categories=DEFAULT_CATEGORIES,
        types=DEFAULT_TYPES,
        agreement_rules={
            "Tech": AgreementRule(
                requires_all=["Ryan", "Ajit"],
                description="Technical decisions require both CEO and CTO agreement",
            ),
            "GTM": AgreementRule(
                requires_any=["Ajit", "Ryan"],
                requires_all=["Milkana"],
                description="GTM decisions require PM and either CEO or CTO",
            ),
        },
    )


def _parse_markdown_participants(content: str) -> list[ParticipantConfig]:
    """
    Extract participants from a markdown table under ## Participants heading.

    Parses tables like:
    | Name | Role | Domain |
    |------|------|--------|
    | **Ryan** | CTO | Engineering |
    | Ajit | CEO | Strategy |
    """
    participants = []
    lines = content.split("\n")
    in_participants_section = False

    for line in lines:
        # check for participants heading (## Participants or ## Participant)
        if line.strip().lower().startswith("## participant"):
            in_participants_section = True
            continue

        # check for next section (any ## heading)
        if in_participants_section and line.strip().startswith("## "):
            break

        # skip horizontal rules (---)
        if in_participants_section and line.strip().startswith("---"):
            continue

        # parse table rows
        if in_participants_section and line.strip().startswith("|"):
            # skip separator rows like |---|---|
            if "---" in line:
                continue

            # parse table row: | **Name** | Role | Domain |
            parts = [p.strip() for p in line.split("|")]
            parts = [p for p in parts if p]  # remove empty strings from split

            if parts:
                # extract name (remove ** bold markers)
                name = parts[0].replace("**", "").strip()

                # skip header row
                if name.lower() == "name":
                    continue

                role = parts[1] if len(parts) > 1 else ""
                participants.append(ParticipantConfig(name=name, role=role))

    return participants


def merge_frameworks(
    base_config: TrackerConfig,
    framework_paths: list[Path],
) -> TrackerConfig:
    """
    Merge multiple decision framework files into a config.

    Frameworks are applied in order (later ones override earlier):
    1. Base config (defaults or loaded YAML)
    2. Team framework (team's standard rules, participants, agreement requirements)
    3. Meeting framework (meeting-specific context, who's present, focus areas)

    Args:
        base_config: Starting configuration
        framework_paths: List of framework markdown/yaml files to apply

    Returns:
        Config with merged frameworks
    """
    import yaml

    config = base_config

    for path in framework_paths:
        if not path.exists():
            continue

        content = path.read_text(encoding="utf-8")

        # check if it's YAML config or markdown framework
        if path.suffix in [".yaml", ".yml"]:
            # YAML config - merge structured fields
            try:
                data = yaml.safe_load(content)
                if data:
                    # merge participants if specified
                    if "participants" in data:
                        participants = []
                        for p in data["participants"]:
                            if isinstance(p, str):
                                participants.append(ParticipantConfig(name=p))
                            else:
                                participants.append(ParticipantConfig(**p))
                        if participants:
                            config.participants = participants
                            config.participants_from_framework = True

                    # merge custom_prompt (append)
                    if "custom_prompt" in data and data["custom_prompt"]:
                        if config.custom_prompt:
                            new_prompt = data["custom_prompt"]
                            config.custom_prompt = f"{config.custom_prompt}\n\n{new_prompt}"
                        else:
                            config.custom_prompt = data["custom_prompt"]

                    # merge agreement rules
                    if "agreement_rules" in data:
                        for key, rule in data["agreement_rules"].items():
                            config.agreement_rules[key] = AgreementRule(**rule)

            except yaml.YAMLError:
                # not valid YAML, treat as markdown
                pass
        else:
            # markdown framework - parse participants and append to custom_prompt
            md_participants = _parse_markdown_participants(content)
            if md_participants:
                config.participants = md_participants
                config.participants_from_framework = True

            if config.custom_prompt:
                framework_text = f"# Framework: {path.name}\n{content}"
                config.custom_prompt = f"{config.custom_prompt}\n\n{framework_text}"
            else:
                config.custom_prompt = f"# Framework: {path.name}\n{content}"

    return config


def load_config(config_path: Path | None = None) -> TrackerConfig:
    """
    Load configuration from a YAML file or return defaults.

    Config file format:

    ```yaml
    custom_prompt: |
      Additional instructions for processing transcripts.
      Customize categories, agreement rules, etc.

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
    ```
    """
    if config_path is None or not config_path.exists():
        return get_default_config()

    with open(config_path, encoding="utf-8") as f:
        data = yaml.safe_load(f)

    if data is None:
        return get_default_config()

    # parse participants
    participants = []
    for p in data.get("participants", []):
        if isinstance(p, str):
            participants.append(ParticipantConfig(name=p))
        else:
            participants.append(ParticipantConfig(**p))

    # parse categories
    categories = []
    for c in data.get("categories", []):
        if isinstance(c, str):
            categories.append(CategoryConfig(name=c))
        else:
            categories.append(CategoryConfig(**c))

    # parse types
    types = []
    for t in data.get("types", []):
        if isinstance(t, str):
            types.append(TypeConfig(name=t))
        else:
            types.append(TypeConfig(**t))

    # parse agreement rules
    agreement_rules = {}
    for key, rule in data.get("agreement_rules", {}).items():
        agreement_rules[key] = AgreementRule(**rule)

    return TrackerConfig(
        custom_prompt=data.get("custom_prompt", ""),
        participants=participants if participants else DEFAULT_PARTICIPANTS,
        categories=categories if categories else DEFAULT_CATEGORIES,
        types=types if types else DEFAULT_TYPES,
        agreement_rules=agreement_rules,
        model=data.get("model", "claude-sonnet-4-20250514"),
        model_provider=data.get("model_provider", "anthropic"),
        default_output_format=data.get("default_output_format", "xlsx"),
    )


def save_config(config: TrackerConfig, config_path: Path) -> None:
    """Save configuration to a YAML file."""
    data: dict[str, Any] = {}

    if config.custom_prompt:
        data["custom_prompt"] = config.custom_prompt

    data["participants"] = [
        {"name": p.name, "role": p.role, "required_for": p.required_for}
        for p in config.participants
    ]

    data["categories"] = [
        {"name": c.name, "description": c.description, "examples": c.examples}
        for c in config.categories
    ]

    data["types"] = [
        {"name": t.name, "description": t.description}
        for t in config.types
    ]

    if config.agreement_rules:
        data["agreement_rules"] = {
            key: {
                "requires_all": rule.requires_all,
                "requires_any": rule.requires_any,
                "description": rule.description,
            }
            for key, rule in config.agreement_rules.items()
        }

    data["model"] = config.model
    data["model_provider"] = config.model_provider
    data["default_output_format"] = config.default_output_format

    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False)


def build_json_extraction_prompt(config: TrackerConfig, transcript: str) -> str:
    """Build extraction prompt that requests JSON output."""
    # load the prompt template from external file
    prompt_template = get_decision_extraction_prompt()

    # build category section
    categories_text = "\n".join(
        f"- **{c.name}**: {c.description}"
        for c in (config.categories if config.categories else DEFAULT_CATEGORIES)
    )

    # build types section
    types_text = "\n".join(
        f"- **{t.name}**: {t.description}"
        for t in (config.types if config.types else DEFAULT_TYPES)
    )

    # build participants section
    participants = config.participants if config.participants else DEFAULT_PARTICIPANTS
    participants_text = ", ".join(p.name for p in participants)
    participant_names = [p.name for p in participants]

    # build agreement rules section
    agreement_rules_text = ""
    if config.agreement_rules:
        rules = []
        for key, rule in config.agreement_rules.items():
            if rule.requires_all:
                all_names = ", ".join(rule.requires_all)
                rules.append(f"- **{key}**: Requires agreement from ALL of: {all_names}")
            if rule.requires_any:
                any_names = ", ".join(rule.requires_any)
                rules.append(f"- **{key}**: Requires agreement from AT LEAST ONE of: {any_names}")
        agreement_rules_text = "\n".join(rules)

    if not agreement_rules_text:
        agreement_rules_text = "Standard agreement rules apply."

    # build example JSON structure for agreements
    example_agreements = ", ".join(f'"{name}": "Yes"' for name in participant_names)

    # build custom prompt section
    custom_prompt_section = ""
    if config.custom_prompt:
        custom_prompt_section = f"## Additional Instructions\n{config.custom_prompt}"

    # format the template with all variables
    prompt = prompt_template.format(
        participants_text=participants_text,
        categories_text=categories_text,
        types_text=types_text,
        agreement_rules_text=agreement_rules_text,
        example_agreements=example_agreements,
        custom_prompt_section=custom_prompt_section,
        transcript=transcript,
    )

    return prompt
