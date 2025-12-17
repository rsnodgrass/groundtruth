#!/usr/bin/env python3
"""
Daily Google Drive Decision Digest

Watches a Google Drive folder (synced locally) for date-based folders and
generates daily decision summaries using Groundtruth.

Setup:
1. Install Google Drive for Desktop (drive.google.com/drive/download)
2. Sync your "Team Decisions" folder locally
3. Set GDRIVE_DECISIONS_PATH to the local sync path
4. Create your team framework file

Usage:
    # Process today's folder
    python daily-gdrive-digest.py

    # Process a specific date
    python daily-gdrive-digest.py --date 2025-12-15

    # Process date range
    python daily-gdrive-digest.py --from 2025-12-09 --to 2025-12-15

    # Run as daily cron job
    0 18 * * * /path/to/daily-gdrive-digest.py >> /var/log/groundtruth.log 2>&1

Expected folder structure:
    ~/Google Drive/Team Decisions/
    ├── frameworks/
    │   ├── team.md              # Your team's decision framework
    │   └── project-phoenix.md   # Project-specific overrides (optional)
    ├── 2025-12-15/
    │   ├── standup-transcript.txt
    │   ├── slack-export.txt
    │   ├── design-review.txt
    │   └── 2025-12-15-Groundtruth.xlsx  # Generated output
    ├── 2025-12-16/
    │   ├── weekly-sync.txt
    │   ├── claude-session.txt
    │   └── 2025-12-16-Groundtruth.xlsx  # Generated output
    └── ...
"""

import argparse
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Configuration
GDRIVE_DECISIONS_PATH = Path.home() / 'Google Drive' / 'Team Decisions'
TEAM_FRAMEWORK = GDRIVE_DECISIONS_PATH / 'frameworks' / 'team.md'
PROJECT_FRAMEWORK = None  # set to path if using project-specific framework
FILE_PATTERNS = ['*.txt', '*.md']  # file types to process
EXCLUDE_PATTERNS = ['*-Groundtruth.csv', '*-Groundtruth.xlsx', 'framework*.md']


def find_date_folders(base_path: Path, start_date: datetime | None = None, end_date: datetime | None = None) -> list[Path]:
    """Find folders named YYYY-MM-DD within date range."""
    folders = []

    for item in base_path.iterdir():
        if not item.is_dir():
            continue

        # try to parse folder name as date
        try:
            folder_date = datetime.strptime(item.name, '%Y-%m-%d')
        except ValueError:
            continue

        # apply date filters
        if start_date and folder_date < start_date:
            continue
        if end_date and folder_date > end_date:
            continue

        folders.append(item)

    return sorted(folders, key=lambda x: x.name)


def has_transcripts(folder: Path) -> bool:
    """Check if folder has any transcript files to process."""
    for pattern in FILE_PATTERNS:
        matches = list(folder.glob(pattern))
        # filter out excluded patterns
        matches = [m for m in matches if not any(m.match(exc) for exc in EXCLUDE_PATTERNS)]
        if matches:
            return True
    return False


def already_processed(folder: Path) -> bool:
    """Check if folder already has a Groundtruth output."""
    date_str = folder.name
    xlsx_file = folder / f'{date_str}-Groundtruth.xlsx'
    return xlsx_file.exists()


def process_folder(folder: Path, frameworks: list[Path], force: bool = False) -> bool:
    """Run groundtruth on a date folder."""
    date_str = folder.name

    if not has_transcripts(folder):
        print(f'  {date_str}: No transcripts found, skipping')
        return False

    if already_processed(folder) and not force:
        print(f'  {date_str}: Already processed, skipping (use --force to reprocess)')
        return False

    # build command
    cmd = ['groundtruth', 'process', str(folder)]

    # add frameworks
    for fw in frameworks:
        if fw.exists():
            cmd.extend(['--framework', str(fw)])

    # add file pattern (combine multiple patterns)
    cmd.extend(['--pattern', '*.txt'])

    print(f'  {date_str}: Processing...')

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        print(f'  {date_str}: Done - {folder / f"{date_str}-Groundtruth.xlsx"}')
        return True
    except subprocess.CalledProcessError as e:
        print(f'  {date_str}: Error - {e.stderr}', file=sys.stderr)
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Process Google Drive date folders with Groundtruth',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        '--date', '-d',
        type=str,
        help='Process specific date (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--from', '-f',
        dest='from_date',
        type=str,
        help='Start date for range (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--to', '-t',
        dest='to_date',
        type=str,
        help='End date for range (YYYY-MM-DD)'
    )
    parser.add_argument(
        '--path', '-p',
        type=Path,
        default=GDRIVE_DECISIONS_PATH,
        help=f'Google Drive folder path (default: {GDRIVE_DECISIONS_PATH})'
    )
    parser.add_argument(
        '--framework',
        type=Path,
        action='append',
        help='Framework file(s) to use (can specify multiple)'
    )
    parser.add_argument(
        '--force',
        action='store_true',
        help='Reprocess folders even if output exists'
    )
    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be processed without running'
    )

    args = parser.parse_args()

    # validate path exists
    base_path = args.path
    if not base_path.exists():
        print(f'Error: Google Drive path not found: {base_path}', file=sys.stderr)
        print('Make sure Google Drive for Desktop is installed and syncing.', file=sys.stderr)
        sys.exit(1)

    # determine date range
    if args.date:
        start_date = datetime.strptime(args.date, '%Y-%m-%d')
        end_date = start_date
    elif args.from_date or args.to_date:
        start_date = datetime.strptime(args.from_date, '%Y-%m-%d') if args.from_date else None
        end_date = datetime.strptime(args.to_date, '%Y-%m-%d') if args.to_date else None
    else:
        # default to today
        start_date = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        end_date = start_date

    # find folders
    folders = find_date_folders(base_path, start_date, end_date)

    if not folders:
        date_range = f'{start_date.strftime("%Y-%m-%d")}' if start_date == end_date else f'{start_date} to {end_date}'
        print(f'No date folders found for {date_range}')
        sys.exit(0)

    # determine frameworks
    frameworks = args.framework or []
    if not frameworks:
        # use defaults
        if TEAM_FRAMEWORK.exists():
            frameworks.append(TEAM_FRAMEWORK)
        if PROJECT_FRAMEWORK and PROJECT_FRAMEWORK.exists():
            frameworks.append(PROJECT_FRAMEWORK)

    if not frameworks:
        print('Warning: No framework files found. Using default extraction rules.', file=sys.stderr)

    # process folders
    print(f'Processing {len(folders)} folder(s) in {base_path}')
    if frameworks:
        print(f'Using frameworks: {", ".join(str(f.name) for f in frameworks)}')
    print()

    processed = 0
    for folder in folders:
        if args.dry_run:
            print(f'  {folder.name}: Would process')
            continue
        if process_folder(folder, frameworks, args.force):
            processed += 1

    print()
    print(f'Processed {processed} folder(s)')


if __name__ == '__main__':
    main()
