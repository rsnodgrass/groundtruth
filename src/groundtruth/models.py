"""Data models for decision tracking."""

from dataclasses import dataclass, field
from enum import Enum


class Significance(Enum):
    """Decision significance level (1=Critical, 5=Minor)."""

    CRITICAL = 1
    EXTREMELY_IMPORTANT = 2
    IMPORTANT = 3
    MODERATE = 4
    SAME_PAGE = 5

    @property
    def label(self) -> str:
        labels = {
            1: "Critical",
            2: "Extremely Important",
            3: "Important",
            4: "Moderate",
            5: "Same Page",
        }
        return labels[self.value]


class Status(Enum):
    """Decision agreement status."""

    AGREED = "Agreed"
    NEEDS_CLARIFICATION = "Needs Clarification"
    UNRESOLVED = "Unresolved"


class AgreementValue(Enum):
    """Individual agreement value."""

    YES = "Yes"
    PARTIAL = "Partial"
    NO = "No"


class Category(Enum):
    """Decision category."""

    GO_TO_MARKET = "Go-to-Market"
    PRODUCT_TIERS = "Product Tiers"
    TECHNICAL_ARCHITECTURE = "Technical Architecture"
    DATA_PRIVACY = "Data & Privacy"
    SECURITY = "Security"
    TERMINOLOGY = "Terminology"
    PROCESS = "Process"


@dataclass
class Agreement:
    """Agreement status for a single participant."""

    name: str
    value: AgreementValue


@dataclass
class Decision:
    """A decision extracted from meeting transcripts.

    Column order: Category, Significance, Status, Title, Description, Decision,
                  [Agreed columns], Notes, Meeting Date, Meeting Reference
    """

    category: Category
    significance: Significance
    status: Status
    title: str
    description: str
    decision: str
    agreements: list[Agreement] = field(default_factory=list)
    notes: str = ""
    meeting_date: str = ""
    meeting_reference: str = ""

    def to_row(self, participants: list[str]) -> list[str]:
        """Convert to CSV row."""
        agreement_map = {a.name: a.value.value for a in self.agreements}
        agreement_values = [agreement_map.get(p, "") for p in participants]

        return [
            self.category.value,
            str(self.significance.value),
            self.status.value,
            self.title,
            self.description,
            self.decision,
            *agreement_values,
            self.notes,
            self.meeting_date,
            self.meeting_reference,
        ]

    @classmethod
    def from_row(cls, row: list[str], participants: list[str]) -> "Decision":
        """Create from CSV row."""
        # map category string to enum
        category_map = {c.value: c for c in Category}
        status_map = {s.value: s for s in Status}
        agreement_map = {a.value: a for a in AgreementValue}

        # parse agreements (start at column 6, after Decision column)
        agreements = []
        agreement_start_idx = 6
        for i, participant in enumerate(participants):
            if agreement_start_idx + i < len(row):
                value_str = row[agreement_start_idx + i]
                if value_str in agreement_map:
                    agreements.append(
                        Agreement(name=participant, value=agreement_map[value_str])
                    )

        # trailing columns after agreements
        notes_idx = agreement_start_idx + len(participants)
        date_idx = notes_idx + 1
        ref_idx = date_idx + 1

        return cls(
            category=category_map.get(row[0], Category.PROCESS),
            significance=(
                Significance(int(row[1]))
                if len(row) > 1 and row[1].isdigit()
                else Significance.IMPORTANT
            ),
            status=status_map.get(row[2], Status.UNRESOLVED) if len(row) > 2 else Status.UNRESOLVED,
            title=row[3] if len(row) > 3 else "",
            description=row[4] if len(row) > 4 else "",
            decision=row[5] if len(row) > 5 else "",
            agreements=agreements,
            notes=row[notes_idx] if len(row) > notes_idx else "",
            meeting_date=row[date_idx] if len(row) > date_idx else "",
            meeting_reference=row[ref_idx] if len(row) > ref_idx else "",
        )


# Default participants
DEFAULT_PARTICIPANTS = ["Ryan", "Ajit", "Milkana"]
