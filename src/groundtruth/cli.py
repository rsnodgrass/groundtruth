"""Command-line interface for Groundtruth."""

import csv
from datetime import datetime
from pathlib import Path

import click
from rich.console import Console
from rich.table import Table

from groundtruth import __version__
from groundtruth.config import (
    get_default_config,
    load_config,
    merge_frameworks,
    save_config,
)
from groundtruth.generator import generate_from_csv, generate_xlsx, get_csv_header
from groundtruth.models import DEFAULT_PARTICIPANTS

console = Console()

# supported transcript file extensions (in priority order)
TRANSCRIPT_EXTENSIONS = [
    ".txt",   # plain text transcripts
    ".vtt",   # WebVTT (common video transcript format)
    ".srt",   # SubRip subtitle format
    ".md",    # markdown notes
    ".json",  # JSON transcripts (e.g., from APIs)
    ".rtf",   # rich text format
]


def find_transcript_files(folder: Path, pattern: str | None = None) -> list[Path]:
    """
    Find transcript files in a folder (case-insensitive extension matching).

    Args:
        folder: Folder to search
        pattern: Optional glob pattern (e.g., "*.txt"). If None, finds all supported types.

    Returns:
        Sorted list of transcript file paths
    """
    if pattern:
        # user specified a pattern, use it directly
        return sorted(folder.glob(pattern))

    # find all files with supported extensions (case-insensitive)
    files: list[Path] = []
    for ext in TRANSCRIPT_EXTENSIONS:
        # match both lowercase and uppercase versions
        files.extend(folder.glob(f"*{ext}"))
        files.extend(folder.glob(f"*{ext.upper()}"))

    # deduplicate and sort
    return sorted(set(files))


def get_output_filename(
    input_path: Path,
    output_name: str | None,
    date_prefix: bool,
    suffix: str = "-Decisions",
) -> str:
    """
    Generate output filename based on input and options.

    Args:
        input_path: Input file or folder path
        output_name: User-specified output name (without extension)
        date_prefix: Whether to add date prefix
        suffix: Suffix to add before extension

    Returns:
        Output filename (without extension)
    """
    if output_name:
        base = output_name
    else:
        # use input stem
        base = input_path.stem
        # remove existing -Decisions or -Groundtruth suffix if present
        if base.endswith("-Decisions"):
            base = base[:-10]
        elif base.endswith("-Groundtruth"):
            base = base[:-12]

    # add suffix if not already present
    if not base.endswith(suffix):
        base = f"{base}{suffix}"

    # add date prefix if enabled and not already present
    if date_prefix:
        today = datetime.now().strftime("%Y-%m-%d")
        # check if already has date prefix (YYYY-MM-DD format)
        if not (len(base) >= 10 and base[:4].isdigit() and base[4] == "-" and base[7] == "-"):
            base = f"{today}-{base}"

    return base


@click.group()
@click.version_option(version=__version__)
def main() -> None:
    """Groundtruth - Extract and track decisions (and non-decisions) from meeting transcripts."""
    pass


@main.command()
@click.argument("transcript", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--output", "-o",
    type=click.Path(path_type=Path),
    help="Output path (defaults to input filename with -Decisions suffix)",
)
@click.option(
    "--output-name", "-n",
    type=str,
    help="Output filename (without extension), overrides auto-naming",
)
@click.option(
    "--config", "-c",
    type=click.Path(exists=True, path_type=Path),
    help="Path to YAML config file for customization",
)
@click.option(
    "--model", "-m",
    type=str,
    help="Model to use (e.g., claude-sonnet-4-20250514, gpt-4)",
)
@click.option(
    "--provider",
    type=click.Choice(["claude-code", "anthropic", "openai", "litellm"]),
    default="claude-code",
    help="Model provider (default: claude-code)",
)
@click.option(
    "--csv",
    is_flag=True,
    help="Also output CSV (XLSX is always generated)",
)
@click.option(
    "--no-date-prefix",
    is_flag=True,
    help="Disable date prefix in output filename",
)
@click.option(
    "--deciders", "-d",
    type=str,
    help="Comma-separated names of decision-makers (overrides config)",
)
@click.option(
    "--prompt",
    type=str,
    help="Custom prompt to add to extraction instructions",
)
@click.option(
    "--framework", "-f",
    type=click.Path(exists=True, path_type=Path),
    multiple=True,
    help="Decision Framework file(s). Can specify multiple. Later ones override earlier.",
)
@click.option(
    "--no-auto-detect",
    is_flag=True,
    help="Disable automatic participant detection from transcript",
)
def extract(
    transcript: Path,
    output: Path | None,
    output_name: str | None,
    config: Path | None,
    model: str | None,
    provider: str,
    csv: bool,
    no_date_prefix: bool,
    deciders: str | None,
    prompt: str | None,
    framework: tuple[Path, ...],
    no_auto_detect: bool,
) -> None:
    """Extract decisions from a transcript using an LLM.

    By default uses Claude Code CLI. Supports any model via LiteLLM.

    Deciders are auto-detected from the transcript unless:
    - Explicitly set via --deciders
    - Defined in a framework file
    - Disabled with --no-auto-detect

    Examples:

        groundtruth extract meeting.txt

        groundtruth extract meeting.txt --provider anthropic --model claude-sonnet-4-20250514

        groundtruth extract meeting.txt -f company-framework.yaml -f meeting-notes.md

        groundtruth extract meeting.txt --csv --output-name "weekly-sync"
    """
    from groundtruth.config import ParticipantConfig, decisions_to_csv_rows
    from groundtruth.llm import extract_decisions_from_transcript_json

    # load config
    tracker_config = load_config(config)

    # merge framework files (in order: company framework, then meeting-specific)
    if framework:
        tracker_config = merge_frameworks(tracker_config, list(framework))
        console.print(f"[dim]Applied {len(framework)} framework file(s)[/dim]")

    # override config with CLI options
    if model:
        tracker_config.model = model
    if provider:
        tracker_config.model_provider = provider
    if deciders:
        tracker_config.participants = [
            ParticipantConfig(name=p.strip())
            for p in deciders.split(",")
        ]
    if prompt:
        tracker_config.custom_prompt = (
            f"{tracker_config.custom_prompt}\n{prompt}"
            if tracker_config.custom_prompt
            else prompt
        )

    console.print(f"[blue]Extracting decisions from:[/blue] {transcript}")
    console.print(f"[dim]Provider: {tracker_config.model_provider}[/dim]")

    # extract decisions using JSON-based extraction (with auto-detection unless disabled)
    result = extract_decisions_from_transcript_json(
        transcript,
        tracker_config,
        auto_detect_participants=not no_auto_detect,
    )
    # convert to CSV rows for output generation
    participant_names = tracker_config.participant_names or result.participants_detected
    rows = decisions_to_csv_rows(result.decisions, participant_names)
    console.print(f"[dim]Participants: {', '.join(participant_names)}[/dim]")

    # read raw framework content for "Produced By" tab (separate from custom_prompt for LLM)
    framework_text = None
    if framework:
        framework_texts = []
        for fw_path in framework:
            framework_texts.append(f"# {fw_path.name}\n{fw_path.read_text(encoding='utf-8')}")
        framework_text = "\n\n".join(framework_texts)

    # determine output path
    if output:
        output_dir = output if output.is_dir() else output.parent
        base_name = get_output_filename(
            transcript if output.is_dir() else output,
            output_name,
            not no_date_prefix,
        )
    else:
        output_dir = transcript.parent
        base_name = get_output_filename(transcript, output_name, not no_date_prefix)

    xlsx_path = output_dir / f"{base_name}.xlsx"

    # generate XLSX (always)
    count = generate_xlsx(
        rows,
        xlsx_path,
        tracker_config.participant_names,
        decision_framework=framework_text,
    )
    console.print(f"[green]Created:[/green] {xlsx_path} ({count} decisions)")

    # generate CSV (optional)
    if csv:
        csv_path = output_dir / f"{base_name}.csv"
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = __import__("csv").writer(f)
            for row in rows:
                writer.writerow(row)
        console.print(f"[green]Created:[/green] {csv_path}")


@main.command()
@click.argument("csv_file", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--output", "-o",
    type=click.Path(path_type=Path),
    help="Output XLSX path (defaults to same name with .xlsx)",
)
@click.option(
    "--deciders", "-d",
    default=",".join(DEFAULT_PARTICIPANTS),
    help=f"Comma-separated names of decision-makers (default: {','.join(DEFAULT_PARTICIPANTS)})",
)
@click.option(
    "--framework", "-f",
    type=click.Path(exists=True, path_type=Path),
    help="Path to Decision Framework markdown file to include in 'Produced By' sheet",
)
def xlsx(csv_file: Path, output: Path | None, deciders: str, framework: Path | None) -> None:
    """Generate formatted XLSX from a Groundtruth CSV."""
    participant_list = [p.strip() for p in deciders.split(",")]

    # read decision framework if provided
    decision_framework = None
    if framework:
        decision_framework = framework.read_text(encoding="utf-8")

    console.print(f"[blue]Processing:[/blue] {csv_file}")
    output_path, count = generate_from_csv(
        csv_file,
        output,
        participant_list,
        decision_framework=decision_framework,
    )
    console.print(f"[green]Created:[/green] {output_path} ({count} decisions)")


@main.command()
@click.argument("csv_file", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--deciders", "-d",
    default=",".join(DEFAULT_PARTICIPANTS),
    help=f"Comma-separated names of decision-makers (default: {','.join(DEFAULT_PARTICIPANTS)})",
)
def validate(csv_file: Path, deciders: str) -> None:
    """Validate a Groundtruth CSV file."""
    participant_list = [p.strip() for p in deciders.split(",")]
    expected_header = get_csv_header(participant_list)

    errors: list[str] = []
    warnings: list[str] = []

    with open(csv_file, newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader, None)

        if header is None:
            errors.append("CSV file is empty")
        elif header != expected_header:
            errors.append(
                f"Header mismatch. Expected {len(expected_header)} columns, got {len(header)}"
            )
            for i, (expected, actual) in enumerate(zip(expected_header, header, strict=False)):
                if expected != actual:
                    errors.append(f"  Column {i+1}: expected '{expected}', got '{actual}'")

        # Validate data rows
        valid_categories = {
            "Go-to-Market", "Product Tiers", "Technical Architecture",
            "Data & Privacy", "Security", "Terminology", "Process"
        }
        valid_types = {"Tech", "Legal", "Compliance", "GTM", "Strategy", "Marketing"}
        valid_statuses = {"Agreed", "Needs Clarification", "Unresolved"}
        valid_agreements = {"Yes", "Partial", "No", ""}

        for row_num, row in enumerate(reader, 2):
            if len(row) < len(expected_header):
                warnings.append(
                    f"Row {row_num}: Missing columns ({len(row)}/{len(expected_header)})"
                )
                continue

            category, dtype, title, sig, desc, decision, status = row[:7]

            if category not in valid_categories:
                warnings.append(f"Row {row_num}: Invalid category '{category}'")

            if dtype not in valid_types:
                warnings.append(f"Row {row_num}: Invalid type '{dtype}'")

            if not sig.isdigit() or not (1 <= int(sig) <= 5):
                errors.append(f"Row {row_num}: Invalid significance '{sig}' (must be 1-5)")

            if status not in valid_statuses:
                errors.append(f"Row {row_num}: Invalid status '{status}'")

            # Check agreement columns
            for i, participant in enumerate(participant_list):
                agreement_idx = 7 + i
                if agreement_idx < len(row):
                    agreement = row[agreement_idx]
                    if agreement not in valid_agreements:
                        errors.append(
                            f"Row {row_num}: Invalid agreement '{agreement}' for {participant}"
                        )

    # Report results
    if errors:
        console.print("[red]Validation FAILED[/red]")
        for error in errors:
            console.print(f"  [red]ERROR:[/red] {error}")
    else:
        console.print("[green]Validation PASSED[/green]")

    if warnings:
        for warning in warnings:
            console.print(f"  [yellow]WARNING:[/yellow] {warning}")

    if not errors and not warnings:
        console.print("  No issues found")


@main.command()
@click.argument("folder", type=click.Path(exists=True, path_type=Path))
@click.option(
    "--from", "from_date",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    help="Start date (YYYY-MM-DD)",
)
@click.option(
    "--to", "to_date",
    type=click.DateTime(formats=["%Y-%m-%d"]),
    help="End date (YYYY-MM-DD)",
)
@click.option(
    "--output", "-o",
    type=click.Path(path_type=Path),
    help="Output path for merged Groundtruth report",
)
@click.option(
    "--output-name", "-n",
    type=str,
    help="Output filename (without extension)",
)
@click.option(
    "--config", "-c",
    type=click.Path(exists=True, path_type=Path),
    help="Path to YAML config file",
)
@click.option(
    "--provider",
    type=click.Choice(["claude-code", "anthropic", "openai", "litellm"]),
    default="claude-code",
    help="Model provider (default: claude-code)",
)
@click.option(
    "--model", "-m",
    type=str,
    help="Model to use",
)
@click.option(
    "--csv",
    is_flag=True,
    help="Also output CSV (XLSX is always generated)",
)
@click.option(
    "--no-date-prefix",
    is_flag=True,
    help="Disable date prefix in output filename",
)
@click.option(
    "--deciders", "-d",
    type=str,
    help="Comma-separated names of decision-makers",
)
@click.option(
    "--pattern",
    type=str,
    default=None,
    help="Glob pattern for files (default: all supported types: .txt, .vtt, .srt, .md, .json)",
)
@click.option(
    "--from-csv",
    is_flag=True,
    help="Process existing CSV files instead of extracting from transcripts",
)
@click.option(
    "--framework", "-f",
    type=click.Path(exists=True, path_type=Path),
    multiple=True,
    help="Decision Framework file(s). Can specify multiple (company, then meeting-specific).",
)
@click.option(
    "--no-auto-detect",
    is_flag=True,
    help="Disable automatic participant detection from transcript",
)
@click.option(
    "--force",
    is_flag=True,
    help="Force regeneration, ignore cached results",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Show what would be processed without doing it",
)
def process(
    folder: Path,
    from_date: datetime | None,
    to_date: datetime | None,
    output: Path | None,
    output_name: str | None,
    config: Path | None,
    provider: str,
    model: str | None,
    csv: bool,
    no_date_prefix: bool,
    deciders: str | None,
    pattern: str | None,
    from_csv: bool,
    framework: tuple[Path, ...],
    no_auto_detect: bool,
    force: bool,
    dry_run: bool,
) -> None:
    """Process meeting transcripts in a folder.

    By default extracts decisions using LLM. Only changed/new files are
    processed (cached results used for unchanged files). Use --force to
    reprocess all files.

    Deciders are auto-detected from transcripts unless explicitly set.

    Examples:

        groundtruth process meetings/2025-12-15/

        groundtruth process meetings/ --from 2025-12-09 --to 2025-12-15

        groundtruth process meetings/ -f company.yaml -f meeting-notes.md

        groundtruth process meetings/ --from-csv

        groundtruth process meetings/ --force

        groundtruth process meetings/ --dry-run
    """
    from groundtruth.config import Decision, ParticipantConfig
    from groundtruth.manifest import (
        FileEntry,
        compute_content_hash,
        create_file_entry,
        create_manifest,
        get_files_to_process,
        load_manifest,
        save_manifest,
    )

    console.print(f"[blue]Scanning:[/blue] {folder}")

    if from_csv:
        # process existing CSV files
        # support both new -Decisions and old -Groundtruth suffixes
        csv_files = list(folder.rglob("*-Decisions.csv")) + list(folder.rglob("*-Groundtruth.csv"))

        if from_date or to_date:
            filtered = []
            for csv_file in csv_files:
                try:
                    date_str = csv_file.stem.replace("-Decisions", "").replace("-Groundtruth", "")
                    file_date = datetime.strptime(date_str, "%Y-%m-%d")
                    if from_date and file_date < from_date:
                        continue
                    if to_date and file_date > to_date:
                        continue
                    filtered.append(csv_file)
                except ValueError:
                    continue
            csv_files = filtered

        if not csv_files:
            console.print("[yellow]No Decisions CSV files found[/yellow]")
            return

        console.print(f"[blue]Found {len(csv_files)} CSV file(s)[/blue]")

        if deciders:
            participant_list = [p.strip() for p in deciders.split(",")]
        else:
            participant_list = DEFAULT_PARTICIPANTS

        # collect custom frameworks (user overrides only) for "Produced By" sheet
        custom_framework = None
        if framework:
            framework_texts = []
            for fw_path in framework:
                framework_texts.append(f"# {fw_path.name}\n{fw_path.read_text(encoding='utf-8')}")
            custom_framework = "\n\n".join(framework_texts)

        total_decisions = 0
        for csv_file in sorted(csv_files):
            output_path, count = generate_from_csv(
                csv_file,
                participants=participant_list,
                decision_framework=custom_framework,
            )
            console.print(f"  [green]Generated:[/green] {output_path.name} ({count} decisions)")
            total_decisions += count

        msg = f"{total_decisions} decisions across {len(csv_files)} file(s)"
        console.print(f"\n[green]Total:[/green] {msg}")
        return

    # extract from transcripts using LLM
    tracker_config = load_config(config)

    # merge framework files (in order)
    if framework:
        tracker_config = merge_frameworks(tracker_config, list(framework))
        console.print(f"[dim]Applied {len(framework)} framework file(s)[/dim]")

    if model:
        tracker_config.model = model
    if provider:
        tracker_config.model_provider = provider
    if deciders:
        tracker_config.participants = [
            ParticipantConfig(name=p.strip())
            for p in deciders.split(",")
        ]

    console.print(f"[dim]Provider: {tracker_config.model_provider}[/dim]")

    # find transcript files
    transcript_files = find_transcript_files(folder, pattern)

    if from_date or to_date:
        filtered = []
        for tf in transcript_files:
            try:
                # try to extract date from filename
                stem = tf.stem
                for part in stem.split("-"):
                    if len(part) == 4 and part.isdigit():
                        idx = stem.find(part)
                        if idx >= 0 and len(stem) >= idx + 10:
                            date_str = stem[idx : idx + 10]
                            if len(date_str.split("-")) == 3:
                                file_date = datetime.strptime(date_str, "%Y-%m-%d")
                                if from_date and file_date < from_date:
                                    break
                                if to_date and file_date > to_date:
                                    break
                                filtered.append(tf)
                                break
            except ValueError:
                filtered.append(tf)  # include files without dates
        transcript_files = filtered

    if not transcript_files:
        ext_list = ", ".join(TRANSCRIPT_EXTENSIONS)
        if pattern:
            console.print(f"[yellow]No files found matching {pattern}[/yellow]")
        else:
            console.print(f"[yellow]No transcript files found ({ext_list})[/yellow]")
        return

    console.print(f"[blue]Found {len(transcript_files)} transcript file(s)[/blue]")

    # determine output directory early (needed for manifest)
    if output:
        output_dir = output if output.is_dir() else output.parent
    else:
        output_dir = folder

    # read raw framework content for hashing and "Produced By" tab
    framework_text = None
    if framework:
        framework_texts = []
        for fw_path in framework:
            framework_texts.append(f"# {fw_path.name}\n{fw_path.read_text(encoding='utf-8')}")
        framework_text = "\n\n".join(framework_texts)

    # compute hashes for change detection
    config_hash = compute_content_hash(tracker_config.custom_prompt)
    framework_hash = compute_content_hash(framework_text or "")

    # load manifest for incremental processing (unless --force)
    manifest = None
    if not force:
        manifest = load_manifest(output_dir)
        if manifest:
            console.print("[dim]Found cached results, checking for changes...[/dim]")

    # determine which files need processing
    files_to_process, cached_decisions = get_files_to_process(
        transcript_files, manifest, config_hash, framework_hash
    )

    # report what will be processed
    if manifest and not force:
        console.print()
        for tf in transcript_files:
            if tf in files_to_process:
                if tf.name in (manifest.files if manifest else {}):
                    console.print(f"  {tf.name}: [yellow]MODIFIED[/yellow]")
                else:
                    console.print(f"  {tf.name}: [cyan]NEW[/cyan]")
            else:
                console.print(f"  {tf.name}: [dim]unchanged (cached)[/dim]")
        console.print()

    # handle --dry-run
    if dry_run:
        console.print("[bold]Dry run - no changes will be made[/bold]")
        cached_count = len(transcript_files) - len(files_to_process)
        console.print(f"Would process {len(files_to_process)} of {len(transcript_files)} files")
        if cached_count > 0:
            console.print(f"Would use cached results for {cached_count} files")
        return

    # skip if nothing to process and we have cached data
    if not files_to_process and cached_decisions:
        console.print("[green]All files unchanged, using cached results[/green]")
    elif files_to_process:
        if force:
            console.print(f"[blue]Processing {len(files_to_process)} files (--force)[/blue]")
        else:
            cached_count = len(transcript_files) - len(files_to_process)
            if cached_count > 0:
                console.print(f"[blue]Processing {len(files_to_process)} changed files "
                              f"({cached_count} cached)[/blue]")
            else:
                console.print(f"[blue]Processing {len(files_to_process)} files[/blue]")

    # extract decisions from changed files using parallel JSON-based extraction
    auto_detect = not bool(deciders)  # skip detection if deciders explicitly provided
    new_decisions: list[Decision] = []
    new_file_entries: dict[str, FileEntry] = {}

    if files_to_process:
        # import here to get per-file decisions
        from groundtruth.llm import extract_decisions_from_transcript_json

        for tf in files_to_process:
            console.print(f"  [dim]Extracting:[/dim] {tf.name}")
            result = extract_decisions_from_transcript_json(
                tf, tracker_config, auto_detect_participants=auto_detect
            )
            new_decisions.extend(result.decisions)

            # create file entry for manifest
            decision_dicts = [d.model_dump() for d in result.decisions]
            new_file_entries[tf.name] = create_file_entry(tf, decision_dicts)

    # merge with cached decisions
    all_decisions: list[Decision] = list(new_decisions)
    for filename, decision_dicts in cached_decisions.items():
        for d in decision_dicts:
            all_decisions.append(Decision(**d))
        # preserve cached file entries in manifest
        if manifest and filename in manifest.files:
            new_file_entries[filename] = manifest.files[filename]

    # convert to CSV rows for output
    from groundtruth.config import decisions_to_csv_rows
    participant_names = tracker_config.participant_names or []
    rows = decisions_to_csv_rows(all_decisions, participant_names)

    base_name = get_output_filename(folder, output_name, not no_date_prefix)
    xlsx_path = output_dir / f"{base_name}.xlsx"

    # generate XLSX (always)
    count = generate_xlsx(
        rows,
        xlsx_path,
        tracker_config.participant_names,
        decision_framework=framework_text,
    )
    console.print(f"[green]Created:[/green] {xlsx_path} ({count} decisions)")

    # save updated manifest
    new_manifest = create_manifest(
        output_file=xlsx_path.name,
        config_hash=config_hash,
        framework_hash=framework_hash,
        file_entries=new_file_entries,
    )
    save_manifest(output_dir, new_manifest)

    # generate CSV (optional)
    if csv:
        csv_path = output_dir / f"{base_name}.csv"
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = __import__("csv").writer(f)
            for row in rows:
                writer.writerow(row)
        console.print(f"[green]Created:[/green] {csv_path}")


@main.command()
@click.option(
    "--deciders", "-d",
    default=",".join(DEFAULT_PARTICIPANTS),
    help=f"Comma-separated names of decision-makers (default: {','.join(DEFAULT_PARTICIPANTS)})",
)
def template(deciders: str) -> None:
    """Print a CSV template with the correct header."""
    participant_list = [p.strip() for p in deciders.split(",")]
    header = get_csv_header(participant_list)
    console.print(",".join(header))


@main.command()
@click.option(
    "--config", "-c",
    type=click.Path(exists=True, path_type=Path),
    help="Path to YAML config file",
)
def categories(config: Path | None) -> None:
    """Show valid categories and types."""
    tracker_config = load_config(config)

    table = Table(title="Categories")
    table.add_column("Category", style="cyan")
    table.add_column("Description")

    for cat in tracker_config.categories:
        table.add_row(cat.name, cat.description)
    console.print(table)

    console.print()

    table2 = Table(title="Types")
    table2.add_column("Type", style="cyan")
    table2.add_column("Description")

    for t in tracker_config.types:
        table2.add_row(t.name, t.description)
    console.print(table2)


@main.command()
@click.argument("output_path", type=click.Path(path_type=Path), default="groundtruth.yaml")
@click.option(
    "--deciders", "-d",
    type=str,
    help="Comma-separated names of decision-makers",
)
@click.option(
    "--force",
    is_flag=True,
    help="Overwrite existing config file",
)
def init(output_path: Path, deciders: str | None, force: bool) -> None:
    """Generate a configuration file template.

    Creates a YAML config file that you can customize with:
    - Custom deciders and their roles
    - Categories and types for your domain
    - Agreement rules (who needs to agree on what)
    - Custom extraction prompts
    - Model provider settings

    Examples:

        groundtruth init

        groundtruth init my-project.yaml -d "Alice,Bob,Carol"
    """
    from groundtruth.config import ParticipantConfig

    if output_path.exists() and not force:
        console.print(f"[red]Error:[/red] {output_path} already exists. Use --force to overwrite.")
        return

    tracker_config = get_default_config()

    if deciders:
        tracker_config.participants = [
            ParticipantConfig(name=p.strip())
            for p in deciders.split(",")
        ]

    # add example custom prompt
    tracker_config.custom_prompt = """# Add your custom instructions here
# Examples:
# - Focus on technical architecture decisions
# - Require unanimous agreement for security decisions
# - Add domain-specific terminology"""

    save_config(tracker_config, output_path)
    console.print(f"[green]Created:[/green] {output_path}")
    console.print("\nEdit this file to customize:")
    console.print("  - deciders: Decision-makers and their roles")
    console.print("  - categories: Decision categories for your domain")
    console.print("  - types: Decision types")
    console.print("  - agreement_rules: Who must agree on what")
    console.print("  - custom_prompt: Additional extraction instructions")
    console.print("  - model_provider: claude-code (default), anthropic, openai, litellm")


@main.command()
@click.option(
    "--config", "-c",
    type=click.Path(exists=True, path_type=Path),
    help="Path to YAML config file",
)
def providers(config: Path | None) -> None:
    """Show supported model providers and configuration."""
    console.print("[bold]Supported Model Providers[/bold]\n")

    table = Table()
    table.add_column("Provider", style="cyan")
    table.add_column("Description")
    table.add_column("Example Model")

    table.add_row(
        "claude-code",
        "Claude Code CLI (default, easiest setup)",
        "Uses installed claude CLI",
    )
    table.add_row(
        "anthropic",
        "Anthropic API via LiteLLM",
        "claude-sonnet-4-20250514",
    )
    table.add_row(
        "openai",
        "OpenAI API via LiteLLM",
        "gpt-4, gpt-4-turbo",
    )
    table.add_row(
        "litellm",
        "Any LiteLLM-supported provider",
        "See litellm.ai/docs/providers",
    )

    console.print(table)

    console.print("\n[bold]Environment Variables[/bold]\n")
    console.print("  ANTHROPIC_API_KEY - For anthropic provider")
    console.print("  OPENAI_API_KEY    - For openai provider")
    console.print("  See LiteLLM docs for other providers")

    console.print("\n[bold]Usage Examples[/bold]\n")
    console.print("  # Use Claude Code CLI (default)")
    console.print("  groundtruth extract meeting.txt")
    console.print()
    console.print("  # Use Anthropic API directly")
    console.print("  groundtruth extract meeting.txt --provider anthropic")
    console.print()
    console.print("  # Use OpenAI")
    console.print("  groundtruth extract meeting.txt --provider openai --model gpt-4")


if __name__ == "__main__":
    main()
