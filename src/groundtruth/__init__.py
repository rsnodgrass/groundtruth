"""Groundtruth - Extract and track decisions (and non-decisions) from meeting transcripts."""

__version__ = "0.1.0"

from groundtruth.generator import generate_from_csv, generate_xlsx
from groundtruth.models import AgreementValue, Decision, Significance, Status

__all__ = [
    "generate_xlsx",
    "generate_from_csv",
    "Decision",
    "Significance",
    "Status",
    "AgreementValue",
]
