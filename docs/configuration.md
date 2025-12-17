# Configuration

Customize Groundtruth for your team's decision-making process.

## Decision Frameworks (Start Here)

The most powerful way to customize Groundtruth is with **Decision Frameworks**—plain English documents that define who needs to agree on what.

**[Read the Decision Frameworks Guide →](decision-frameworks.md)**

Frameworks let you:
- Define your team's decision-makers and their roles
- Specify agreement requirements by decision type and significance
- Handle ambiguous situations consistently
- Layer multiple frameworks: **team → project → meeting**

```bash
# Layer frameworks (later ones override earlier)
groundtruth extract meeting.txt --framework team.md --framework project.md --framework meeting.md
```

---

## YAML Configuration

For programmatic configuration, use YAML config files:

```bash
# Generate config template
groundtruth init my-config.yaml -d "Alice,Bob,Carol"

# Use custom config
groundtruth extract meeting.txt --config my-config.yaml
```

### Config Options

| Option | Description |
|--------|-------------|
| `participants` | Team members and their roles |
| `categories` | Decision categories for your domain |
| `types` | Decision types (Tech, Legal, etc.) |
| `agreement_rules` | Who must agree on what decisions |
| `custom_prompt` | Additional LLM instructions |
| `model_provider` | Default LLM provider |

### Example Config

```yaml
custom_prompt: |
  Focus on technical architecture decisions.
  Require unanimous agreement for security decisions.

participants:
  - name: Alice
    role: CEO
    required_for: [Strategy, GTM]
  - name: Bob
    role: CTO
    required_for: [Tech]
  - name: Carol
    role: Product Manager
    required_for: [GTM]

agreement_rules:
  Tech:
    requires_all: [Alice, Bob]
    description: Tech decisions require both CEO and CTO
  GTM:
    requires_all: [Carol]
    requires_any: [Alice, Bob]
    description: GTM requires PM and either CEO or CTO

model_provider: claude-code
```

---

## Automatic Participant Detection

By default, Groundtruth analyzes transcripts to detect deciders.

Detection is skipped if:
- Participants defined in a framework file
- Participants set via `--deciders` flag
- Disabled with `--no-auto-detect`

```bash
# Auto-detect (default)
groundtruth extract meeting.txt

# Explicitly specify deciders
groundtruth extract meeting.txt -d "Alice,Bob,Carol"

# Disable auto-detection
groundtruth extract meeting.txt --no-auto-detect
```

---

## LLM Providers (BYOM)

Claude Code CLI is recommended and tested. Other providers are experimental.

```bash
# Default: Claude Code CLI
groundtruth extract meeting.txt

# EXPERIMENTAL: Anthropic API
export ANTHROPIC_API_KEY=your-key
groundtruth extract meeting.txt --provider anthropic --model claude-sonnet-4-20250514

# EXPERIMENTAL: OpenAI
export OPENAI_API_KEY=your-key
groundtruth extract meeting.txt --provider openai --model gpt-4

# Any LiteLLM provider
groundtruth extract meeting.txt --provider litellm --model your-model
```

See `groundtruth providers` for full provider documentation.

---

## Integration with Claude Code

Add to your project's `CLAUDE.md`:

```markdown
## Meeting Processing

When processing meeting transcripts, use Groundtruth:

1. Read all transcript files in the dated folder
2. Extract decisions using the team framework
3. Generate CSV with proper columns and sorting
4. Generate formatted XLSX
5. Update root README with Groundtruth link

Framework: See frameworks/team.md for decision rules.
```

---

## See Also

- **[Decision Frameworks Guide](decision-frameworks.md)** - Create team/project/meeting frameworks
- [Getting Started](getting-started.md) - Installation and first extraction
- [CLI Reference](cli-reference.md) - All commands and options
- [Decision Tracking Guide](decision-tracking-guide.md) - Understanding output
