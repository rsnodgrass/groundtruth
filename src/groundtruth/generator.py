"""XLSX generator for Groundtruth reports."""

import csv
import os
from datetime import datetime
from pathlib import Path
from typing import Any

from openpyxl import Workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.worksheet.worksheet import Worksheet

from groundtruth.models import DEFAULT_PARTICIPANTS

# Color schemes
HEADER_FILL = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
HEADER_FONT = Font(bold=True, color="FFFFFF")

# Significance colors (blue gradient: vibrant blue -> almost white)
SIGNIFICANCE_COLORS = {
    "1": PatternFill(start_color="0d47a1", end_color="0d47a1", fill_type="solid"),  # vibrant dark blue
    "2": PatternFill(start_color="1976d2", end_color="1976d2", fill_type="solid"),  # medium-dark blue
    "3": PatternFill(start_color="42a5f5", end_color="42a5f5", fill_type="solid"),  # medium blue
    "4": PatternFill(start_color="90caf9", end_color="90caf9", fill_type="solid"),  # light blue
    "5": PatternFill(start_color="e3f2fd", end_color="e3f2fd", fill_type="solid"),  # very light blue
}

# Significance font colors (white for dark backgrounds, black for light)
SIGNIFICANCE_FONTS = {
    "1": Font(bold=True, color="FFFFFF"),
    "2": Font(bold=True, color="FFFFFF"),
    "3": Font(bold=False, color="000000"),
    "4": Font(bold=False, color="000000"),
    "5": Font(bold=False, color="000000"),
}

# Status colors
STATUS_COLORS = {
    "Agreed": PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid"),
    "Needs Clarification": PatternFill(start_color="FFEB9C", end_color="FFEB9C", fill_type="solid"),
    "Unresolved": PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid"),
}

# Agreement colors
AGREEMENT_COLORS = {
    "No": PatternFill(start_color="FFC7CE", end_color="FFC7CE", fill_type="solid"),
    "Partial": PatternFill(start_color="FFEB9C", end_color="FFEB9C", fill_type="solid"),
    "Yes": PatternFill(start_color="C6EFCE", end_color="C6EFCE", fill_type="solid"),
}

# Standard styles
WRAP_ALIGNMENT = Alignment(wrap_text=True, vertical="top")
CENTER_ALIGNMENT = Alignment(wrap_text=True, vertical="top", horizontal="center")
HEADER_ALIGNMENT = Alignment(wrap_text=True, vertical="center", horizontal="center")
THIN_BORDER = Border(
    left=Side(style="thin"),
    right=Side(style="thin"),
    top=Side(style="thin"),
    bottom=Side(style="thin"),
)

# Column order:
# Category, Significance, Status, Title, Description, Decision, [Agreed], Notes, Meeting Date, Ref
COLUMN_ORDER = [
    ("Category", 20, False),
    ("Significance", 10, True),
    ("Status", 18, True),
    ("Title", 28, False),
    ("Description", 55, False),
    ("Decision", 30, False),
    # Agreed columns inserted dynamically
    # Notes, Meeting Date, Meeting Reference appended after
]

TRAILING_COLUMNS = [
    ("Notes", 45, False),
    ("Meeting Date", 12, True),
    ("Meeting Reference", 28, False),
]


def get_column_config(participants: list[str]) -> dict[str, dict[str, Any]]:
    """Get column configuration based on participants."""
    config: dict[str, dict[str, Any]] = {}
    col_letters = "ABCDEFGHIJKLMNOPQRSTUVWXYZ"

    col_idx = 0

    # base columns before agreed columns
    for name, width, center in COLUMN_ORDER:
        config[col_letters[col_idx]] = {"name": name, "width": width, "center": center}
        col_idx += 1

    # agreed columns for each participant
    for participant in participants:
        config[col_letters[col_idx]] = {
            "name": f"{participant} Agreed",
            "width": 12,
            "center": True,
        }
        col_idx += 1

    # trailing columns
    for name, width, center in TRAILING_COLUMNS:
        config[col_letters[col_idx]] = {"name": name, "width": width, "center": center}
        col_idx += 1

    return config


def apply_cell_style(
    ws: Worksheet,
    row_idx: int,
    col_idx: int,
    value: str,
    is_header: bool,
    col_config: dict[str, Any],
    participants: list[str],
) -> None:
    """Apply styling to a cell."""
    cell = ws.cell(row=row_idx, column=col_idx, value=value)
    cell.border = THIN_BORDER

    if is_header:
        cell.font = HEADER_FONT
        cell.fill = HEADER_FILL
        cell.alignment = HEADER_ALIGNMENT
        return

    # data row styling
    cell.alignment = CENTER_ALIGNMENT if col_config.get("center") else WRAP_ALIGNMENT

    # significance column (B = 2)
    if col_idx == 2 and value in SIGNIFICANCE_COLORS:
        cell.fill = SIGNIFICANCE_COLORS[value]
        cell.font = SIGNIFICANCE_FONTS.get(value, Font())

    # status column (C = 3)
    if col_idx == 3 and value in STATUS_COLORS:
        cell.fill = STATUS_COLORS[value]

    # agreement columns (start at G = 7)
    agreement_start = 7
    agreement_end = agreement_start + len(participants)
    if agreement_start <= col_idx < agreement_end and value in AGREEMENT_COLORS:
        cell.fill = AGREEMENT_COLORS[value]
        if value in ["No", "Partial"]:
            cell.font = Font(bold=True)


def add_summary_sheet(
    wb: Workbook,
    rows: list[list[str]],
    participants: list[str],
) -> None:
    """Add summary sheet with meeting metadata."""
    ws = wb.create_sheet(title="Summary")

    # title
    ws["A1"] = "Meeting Summary"
    ws["A1"].font = Font(bold=True, size=16)

    # extract unique meeting dates and references from data
    meeting_dates: set[str] = set()
    meeting_refs: set[str] = set()
    data_rows = rows[1:]  # skip header

    # meeting date is in trailing columns after agreed columns
    date_col_idx = 6 + len(participants)  # Notes=6+n, Date=7+n, Ref=8+n
    ref_col_idx = date_col_idx + 1

    for row in data_rows:
        if len(row) > date_col_idx and row[date_col_idx]:
            meeting_dates.add(row[date_col_idx])
        if len(row) > ref_col_idx and row[ref_col_idx]:
            meeting_refs.add(row[ref_col_idx])

    # participants section
    ws["A3"] = "Participants"
    ws["A3"].font = Font(bold=True)
    for i, participant in enumerate(participants):
        ws[f"B{3 + i}"] = participant

    row_num = 3 + len(participants) + 1

    # meeting dates section
    ws[f"A{row_num}"] = "Meeting Dates"
    ws[f"A{row_num}"].font = Font(bold=True)
    for i, date in enumerate(sorted(meeting_dates)):
        ws[f"B{row_num + i}"] = date
    row_num += max(len(meeting_dates), 1) + 1

    # transcript references section
    ws[f"A{row_num}"] = "Transcript Files"
    ws[f"A{row_num}"].font = Font(bold=True)
    for i, ref in enumerate(sorted(meeting_refs)):
        ws[f"B{row_num + i}"] = ref
    row_num += max(len(meeting_refs), 1) + 1

    # decision count
    ws[f"A{row_num}"] = "Total Decisions"
    ws[f"A{row_num}"].font = Font(bold=True)
    ws[f"B{row_num}"] = len(data_rows)

    # set column widths
    ws.column_dimensions["A"].width = 18
    ws.column_dimensions["B"].width = 40


def add_attribution_sheet(
    wb: Workbook,
    user_name: str | None = None,
    user_email: str | None = None,
    decision_framework: str | None = None,
) -> None:
    """Add attribution sheet to workbook."""
    ws = wb.create_sheet(title="Produced By")

    # title
    ws["A1"] = "Groundtruth"
    ws["A1"].font = Font(bold=True, size=16)

    ws["A3"] = "Tool"
    ws["A3"].font = Font(bold=True)
    ws["B3"] = "groundtruth"

    ws["A4"] = "Repository"
    ws["A4"].font = Font(bold=True)
    ws["B4"] = "https://github.com/rsnodgrass/groundtruth"

    ws["A5"] = "Generated"
    ws["A5"].font = Font(bold=True)
    ws["B5"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    row = 6
    if user_name:
        ws[f"A{row}"] = "Author"
        ws[f"A{row}"].font = Font(bold=True)
        ws[f"B{row}"] = user_name
        row += 1

    if user_email:
        ws[f"A{row}"] = "Email"
        ws[f"A{row}"].font = Font(bold=True)
        ws[f"B{row}"] = user_email
        row += 1

    # quick reference: significance levels and agreement standards
    row += 2
    ws[f"A{row}"] = "Quick Reference: Significance & Agreement Standards"
    ws[f"A{row}"].font = Font(bold=True, size=14)

    row += 2
    significance_ref = [
        ("Level", "Label", "Agreement Standard"),
        ("1", "Critical", "ALL must explicitly agree; any ambiguity = No"),
        ("2", "Extremely Important", "ALL must explicitly agree; any ambiguity = No"),
        ("3", "Important", "Any hint of misalignment = Partial or No"),
        ("4", "Moderate", "Clear alignment; slight ambiguity OK"),
        ("5", "Same Page", "General alignment sufficient"),
    ]

    for i, (level, label, standard) in enumerate(significance_ref):
        ws[f"A{row}"] = level
        ws[f"B{row}"] = label
        ws[f"C{row}"] = standard
        if i == 0:
            ws[f"A{row}"].font = Font(bold=True)
            ws[f"B{row}"].font = Font(bold=True)
            ws[f"C{row}"].font = Font(bold=True)
        row += 1

    row += 1
    ws[f"A{row}"] = "Agreement: Yes (explicit), Partial (hedged), No (silent/parked/disagreed)"
    ws[f"A{row}"].font = Font(italic=True)

    # user's custom framework (overrides only)
    if decision_framework:
        row += 3
        ws[f"A{row}"] = "Custom Decision Framework"
        ws[f"A{row}"].font = Font(bold=True, size=14)
        row += 1
        ws[f"A{row}"] = "User-provided customizations that guided extraction:"
        ws[f"A{row}"].font = Font(italic=True)
        row += 2

        # write the decision framework text, handling multi-line content
        framework_lines = decision_framework.strip().split("\n")
        for line in framework_lines:
            ws[f"A{row}"] = line
            ws[f"A{row}"].alignment = Alignment(wrap_text=True)
            row += 1

    # set column widths
    ws.column_dimensions["A"].width = 25
    ws.column_dimensions["B"].width = 25
    ws.column_dimensions["C"].width = 50


def generate_xlsx(
    rows: list[list[str]],
    output_path: Path,
    participants: list[str] | None = None,
    user_name: str | None = None,
    user_email: str | None = None,
    decision_framework: str | None = None,
) -> int:
    """
    Generate formatted XLSX from decision data.

    Args:
        rows: List of rows including header
        output_path: Path to save XLSX
        participants: List of participant names
        user_name: Optional user name for attribution
        user_email: Optional user email for attribution
        decision_framework: Optional custom prompt that guided decision extraction

    Returns:
        Number of decisions (excluding header)
    """
    if participants is None:
        participants = DEFAULT_PARTICIPANTS

    # try to get user info from environment
    if user_name is None:
        user_name = os.environ.get("USER") or os.environ.get("USERNAME")
    if user_email is None:
        user_email = os.environ.get("EMAIL")

    # sort data by Category, then Significance
    header = rows[0]
    data = rows[1:]

    # find significance column index (should be 2 in new order)
    sig_col_idx = 2
    data.sort(
        key=lambda x: (
            x[0] if x else "",
            int(x[sig_col_idx]) if len(x) > sig_col_idx and x[sig_col_idx].isdigit() else 99,
        )
    )
    sorted_rows = [header] + data

    # create workbook
    wb = Workbook()
    ws = wb.active
    if ws is None:
        raise RuntimeError("Failed to create worksheet")
    ws.title = "Groundtruth"

    # get column configuration
    col_config = get_column_config(participants)

    # set column widths
    for col_letter, config in col_config.items():
        ws.column_dimensions[col_letter].width = config["width"]

    # write data with styling
    for row_idx, row_data in enumerate(sorted_rows, 1):
        is_header = row_idx == 1
        for col_idx, value in enumerate(row_data, 1):
            col_letter = chr(ord("A") + col_idx - 1)
            config = col_config.get(col_letter, {"center": False})
            apply_cell_style(ws, row_idx, col_idx, value, is_header, config, participants)

    # freeze header and set row heights
    ws.freeze_panes = "A2"
    ws.row_dimensions[1].height = 35
    for row_idx in range(2, len(sorted_rows) + 1):
        ws.row_dimensions[row_idx].height = 60

    # add summary sheet
    add_summary_sheet(wb, sorted_rows, participants)

    # add attribution sheet
    add_attribution_sheet(wb, user_name, user_email, decision_framework)

    # save
    wb.save(output_path)
    return len(sorted_rows) - 1


def generate_from_csv(
    csv_path: Path,
    output_path: Path | None = None,
    participants: list[str] | None = None,
    decision_framework: str | None = None,
) -> tuple[Path, int]:
    """
    Generate XLSX from a CSV file.

    Args:
        csv_path: Path to CSV file
        output_path: Optional output path (defaults to same name with .xlsx)
        participants: List of participant names
        decision_framework: Optional custom prompt that guided decision extraction

    Returns:
        Tuple of (output path, decision count)
    """
    if output_path is None:
        output_path = csv_path.with_suffix(".xlsx")

    # read CSV
    rows: list[list[str]] = []
    with open(csv_path, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        for row in reader:
            rows.append(row)

    count = generate_xlsx(rows, output_path, participants, decision_framework=decision_framework)
    return output_path, count


def get_csv_header(participants: list[str] | None = None) -> list[str]:
    """Get the standard CSV header row."""
    if participants is None:
        participants = DEFAULT_PARTICIPANTS

    return [
        "Category",
        "Significance",
        "Status",
        "Title",
        "Description",
        "Decision",
        *[f"{p} Agreed" for p in participants],
        "Notes",
        "Meeting Date",
        "Meeting Reference",
    ]
