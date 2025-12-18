# Getting Started

Get up and running with Groundtruth in 5 minutes.

## Prerequisites

### Python 3.14+

Install via Homebrew on macOS:

```bash
brew install python@3.14
```

### Claude Code (Recommended)

Recommended for decision extraction. Install from https://claude.ai/code or:

```bash
npm install -g @anthropic-ai/claude-code
```

## Installation

### Via pip

```bash
pip install groundtruth
```

### From source

```bash
git clone https://github.com/rsnodgrass/groundtruth.git
cd groundtruth
pip install -e .
```

## Your First Extraction

### 1. Prepare a transcript

Your transcript needs speaker attribution (who said what):

```
Alice: I think we should use PostgreSQL for this.
Bob: Agreed. Let's go with PostgreSQL.
Alice: Great, that's decided then.
```

Most transcription services (Otter.ai, Rev, Fireflies, Descript) provide this automatically.

### 2. Run extraction

```bash
groundtruth extract meeting-transcript.txt
```

### 3. Review output

Open the generated XLSX file to see:
- Each decision as a row
- Significance rating (1-5)
- Agreement status per person
- Color-coded formatting

## Basic Usage

```bash
# Extract from single transcript
groundtruth extract meeting-transcript.txt

# Process all transcripts in a folder
groundtruth process meetings/2025-12-15/

# Process with date range
groundtruth process meetings/ --from 2025-12-09 --to 2025-12-15

# Generate XLSX from existing CSV
groundtruth xlsx meetings/2025-12-15/2025-12-15-Decisions.csv
```

## Understanding Output

Every decision includes:
- **Category** - Logical grouping (Technical Architecture, Go-to-Market, etc.)
- **Type** - Decision type (Tech, Legal, GTM, Strategy, etc.)
- **Significance** - 1 (Critical) to 5 (Minor)
- **Status** - Agreed / Needs Clarification / Unresolved
- **Per-person agreement** - Yes / Partial / No for each participant

## Efficient Reprocessing

Groundtruth automatically caches extraction results. Running `process` again only extracts from new or modified files:

```bash
$ groundtruth process meetings/

Found cached results, checking for changes...
  meeting-1.txt: unchanged (cached)
  meeting-2.txt: MODIFIED

Processing 1 changed files (1 cached)
Created: 2025-12-17-meetings-Decisions.xlsx (8 decisions)
```

To force full reprocessing:

```bash
groundtruth process meetings/ --force
```

To preview what would be processed without running:

```bash
groundtruth process meetings/ --dry-run
```

## Post-Processing Checklist

After generating reports:

1. **Review Significance 1-2 items** - Ensure agreement assessments are strict
2. **Flag Unresolved items** - Add to next meeting agenda
3. **Update project README** - Link to Groundtruth files
4. **Share with team** - Sync to shared drive if needed

## Next Steps

- **[Decision Frameworks](decision-frameworks.md)** - Define who must agree on what for your team
- [Configuration](configuration.md) - YAML config and LLM providers
- [CLI Reference](cli-reference.md) - All commands and options
- [Meeting Best Practices](meeting-best-practices.md) - Run better meetings
