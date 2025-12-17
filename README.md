# Groundtruth

> **Your company makes hundreds of decisions a week. How many does your team actually remember?**

Decisions happen everywhere—standups, Slack threads, PR reviews, design docs, AI coding sessions. By Friday, nobody remembers what was decided Monday.

**Groundtruth captures it all.** Feed in transcripts, chat logs, or meeting notes. Get a structured spreadsheet showing every decision, who made it, and whether everyone actually agreed.

More importantly: it tracks **non-decisions**—the parked topics, unresolved debates, and false agreements where someone nodded but never signed off.

**Result: 10x better team alignment.**

```mermaid
flowchart LR
    A["Transcripts, Slack,<br>Git logs, AI sessions"] -->|analyze| B{{"groundtruth"}} -->|extract| C[("Decisions Excel")]
    style A fill:#1e3a5f,color:#fff
    style B fill:#ef476f,color:#fff
    style C fill:#06d6a0,color:#000
```

---

## Quick Start

```bash
# Install
pip install groundtruth

# Extract decisions from a transcript
groundtruth extract meeting-transcript.txt

# Process a folder of meetings
groundtruth process meetings/2025-12-15/
```

**[Full installation guide →](docs/getting-started.md)**

---

## Why This Matters Now

Pre-2023, startups made 10-20 decisions per week. Now, with AI-assisted development, that's 10x higher. Architecture decisions happen mid-coding session. Product pivots emerge from midnight Slack threads.

**The fastest teams aren't those making the most decisions. They're the ones where everyone knows what was decided.**

---

## Key Features

- **Multi-source** — Process meetings, Slack, git logs, AI sessions—anything text-based
- **Non-decision tracking** — Capture what hasn't been decided, not just what has
- **False agreement detection** — Identify when people nod but don't actually agree
- **Significance-based rules** — Conservative agreement assessment for critical decisions
- **Bring your own LLM** — Works with Claude Code (recommended), Anthropic API, OpenAI, or LiteLLM
- **[Decision Frameworks](docs/decision-frameworks.md)** — Define who must agree on what, with layered team → project → meeting rules

---

## Decision Frameworks

The real power of Groundtruth comes from **Decision Frameworks**—plain English documents that define how your team makes decisions.

```bash
# Layer frameworks: team defaults → project overrides → meeting context
groundtruth extract meeting.txt --framework team.md --framework project.md --framework meeting.md
```

A framework specifies:
- **Who** your decision-makers are (Alice is CEO, Bob is CTO...)
- **What** agreement is required ("Tech Sig 1: Alice AND Bob MUST agree")
- **How** to handle ambiguity ("Default if unclear: No")

**[Create your team's Decision Framework →](docs/decision-frameworks.md)**

---

## Use Cases

**Daily Decision Digest** — Process everything from today with your team framework:
```bash
groundtruth process today/ --framework team.md
```

**Weekly Alignment Report** — Layer team + project frameworks:
```bash
groundtruth process week-of-dec-16/ --framework team.md --framework project.md --pattern "*.txt"
```

**AI Coding Session Audit** — Capture architectural decisions with full context:
```bash
groundtruth extract claude-session.txt --framework team.md --framework project.md --framework meeting.md
```

**Cross-Team Sync** — Use company-wide framework for multi-team alignment:
```bash
groundtruth process q4-planning/ --framework company.md --framework cross-team-sync.md
```

**Board Updates** — Professional decision tracking for governance:
```bash
groundtruth process board-meetings/ --framework board.md --output board-decisions.xlsx
```

---

## Documentation

| Guide | Description |
|-------|-------------|
| **[Decision Frameworks](docs/decision-frameworks.md)** | **Start here** — Define who must agree on what for your team |
| **[Getting Started](docs/getting-started.md)** | Installation, first extraction, understanding output |
| **[Configuration](docs/configuration.md)** | YAML config, LLM providers, Claude Code integration |
| **[CLI Reference](docs/cli-reference.md)** | All commands and options |
| **[Decision Tracking Guide](docs/decision-tracking-guide.md)** | Significance scale, agreement rules, output format |
| **[Meeting Best Practices](docs/meeting-best-practices.md)** | Run meetings that produce great extraction |
| **[Contributing](docs/contributing.md)** | Development setup, testing, how to contribute |

---

## Requirements

- **Python 3.14+**
- **Claude Code** — Recommended for decision extraction (if you use anything else you are on your own to figure out how to make this work!). Install from https://claude.ai/code
- **Speaker attribution in transcripts** — Most transcription services (Otter.ai, Rev, Fireflies, Descript) provide this automatically

---

## Example Output

Every decision includes:
- Category, Type, Significance (1-5 scale)
- Full description with context
- Agreement status (Agreed / Needs Clarification / Unresolved)
- Per-person agreement (Yes / Partial / No)
- Evidence from transcript

See `examples/` for sample transcripts and generated reports.

---

## License

MIT License - see [LICENSE](LICENSE) for details.

---

## Contributing

Contributions welcome! See [docs/contributing.md](docs/contributing.md) for details.

Key areas: agreement detection heuristics, transcript format support, visualization features.

---

## Support

- **Issues**: [GitHub Issues](https://github.com/rsnodgrass/groundtruth/issues)
- **Discussions**: [GitHub Discussions](https://github.com/rsnodgrass/groundtruth/discussions)
- **Examples**: [examples/](examples/)

---

**Built for teams moving fast. Track decisions, not chaos.**
