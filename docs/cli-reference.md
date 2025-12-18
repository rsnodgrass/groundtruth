# CLI Reference

Complete command-line reference for Groundtruth.

## Commands

### extract

Extract decisions from a transcript (primary command).

```bash
groundtruth extract <transcript> [options]
```

| Option | Description |
|--------|-------------|
| `--framework PATH` | Decision framework file (can specify multiple, **order matters**: later overrides earlier) |
| `--output, -o PATH` | Output path |
| `--output-name, -n NAME` | Output filename (without extension) |
| `--config, -c PATH` | YAML config file for customization |
| `--model, -m MODEL` | LLM model to use |
| `--provider PROVIDER` | Model provider: claude-code (default), anthropic, openai, litellm |
| `--csv` | Also output CSV (XLSX is always generated) |
| `--no-date-prefix` | Disable date prefix in output filename |
| `--deciders, -d LIST` | Comma-separated names of decision-makers |
| `--prompt TEXT` | Custom prompt to add to extraction |

### process

Process all transcripts in a folder.

```bash
groundtruth process <folder> [options]
```

| Option | Description |
|--------|-------------|
| `--framework PATH` | Decision framework file (can specify multiple, **order matters**: later overrides earlier) |
| `--from DATE` | Start date (YYYY-MM-DD) |
| `--to DATE` | End date (YYYY-MM-DD) |
| `--output, -o PATH` | Output path |
| `--output-name, -n NAME` | Output filename |
| `--config, -c PATH` | YAML config file |
| `--provider PROVIDER` | Model provider |
| `--model, -m MODEL` | LLM model |
| `--csv` | Also output CSV |
| `--no-date-prefix` | Disable date prefix |
| `--deciders, -d LIST` | Names of decision-makers |
| `--pattern GLOB` | Transcript file pattern (default: all supported types) |
| `--from-csv` | Process existing CSVs instead of transcripts |
| `--force` | Force regeneration, ignore cached results |
| `--dry-run` | Show what would be processed without doing it |

### xlsx

Generate XLSX from CSV.

```bash
groundtruth xlsx <csv-file> [options]
```

| Option | Description |
|--------|-------------|
| `--output, -o PATH` | Output XLSX path |
| `--deciders, -d LIST` | Names of decision-makers |

### validate

Validate a Groundtruth CSV.

```bash
groundtruth validate <csv-file>
```

### Configuration Commands

```bash
groundtruth init [output.yaml]    # Generate config template
groundtruth categories            # Show valid categories/types
groundtruth providers             # Show supported LLM providers
groundtruth template              # Print CSV header
```

## Output Naming

By default:
- **Single transcript**: `{input-name}-Decisions.xlsx`
- **Multiple transcripts**: `{folder-name}-Decisions.xlsx`
- **Date prefix**: `2025-12-15-{name}-Decisions.xlsx` (default, disable with `--no-date-prefix`)
- **Custom name**: Use `--output-name` to override

## Incremental Processing

By default, `groundtruth process` tracks which files have been processed in a `.groundtruth.json` manifest. On subsequent runs, only changed or new files are reprocessed - unchanged files use cached results.

```bash
$ groundtruth process meetings/

Found cached results, checking for changes...
  meeting-1.txt: unchanged (cached)
  meeting-2.txt: MODIFIED
  meeting-3.txt: NEW

Processing 2 changed files (1 cached)
```

- Use `--force` to reprocess all files regardless of cache
- Use `--dry-run` to preview what would be processed without doing it

The manifest stores:
- File hashes (SHA-256) for change detection
- Cached decisions from previous extractions
- Config and framework hashes (changes trigger full reprocessing)

## Examples

```bash
# Basic extraction
groundtruth extract meeting.txt

# With custom deciders
groundtruth extract meeting.txt -d "Alice,Bob,Carol"

# Process week with pattern
groundtruth process week-of-dec-16/ --pattern "*.txt"

# Use custom config
groundtruth extract meeting.txt -c team-config.yaml

# Layer frameworks
groundtruth extract meeting.txt -f team.yaml -f meeting.md

# OpenAI provider
groundtruth extract meeting.txt --provider openai --model gpt-4

# Force reprocessing all files
groundtruth process meetings/ --force

# Preview what would be processed
groundtruth process meetings/ --dry-run
```

## See Also

- **[Decision Frameworks](decision-frameworks.md)** - Define who must agree on what for your team
- [Getting Started](getting-started.md) - Installation and first extraction
- [Configuration](configuration.md) - YAML config and LLM providers
- [Decision Tracking Guide](decision-tracking-guide.md) - Understanding output
