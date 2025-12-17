# Decision Tracking Guide

Complete reference for understanding Groundtruth output.

## Decision Anatomy

Every decision extracted includes these fields:

| Field | Description |
|-------|-------------|
| **Category** | Logical grouping (Go-to-Market, Technical Architecture, etc.) |
| **Type** | Decision type (Tech, Legal, Compliance, GTM, Strategy, Marketing) |
| **Title** | Short name (3-8 words) |
| **Significance** | 1-5 scale (1=Critical, 5=Minor) |
| **Description** | Full context with problem, considerations, and outcome |
| **Decision** | What was decided, or "No decision reached" |
| **Status** | Agreed / Needs Clarification / Unresolved |
| **[Person] Agreed** | Yes / Partial / No for each participant |
| **Meeting Date** | YYYY-MM-DD |
| **Notes** | Evidence from transcript, quotes |
| **Meeting Reference** | Transcript filename(s) |

## Significance Scale

Decisions are rated 1-5 based on reversibility, impact, and dependencies.

| Level | Label | Meaning | Examples |
|-------|-------|---------|----------|
| **1** | Critical | Existential or near-irreversible | Company pivot; One-way-door architecture; Legal/compliance commitments |
| **2** | Extremely Important | Foundational, difficult to change | Core architecture; Technology stack; Pricing model; Target market |
| **3** | Important | Significant impact, reversible with effort | Feature scope; API design; Data models; Third-party integrations |
| **4** | Moderate | Useful alignment, some effort to reverse | Implementation approach; Tool selection; Process decisions |
| **5** | Same Page | Easily reversible, good to be aligned | Terminology; Minor UX; File organization |

### Assignment Guidelines

- **Default to 3** if unsure, then adjust
- **Lower number (more critical) if:** Harder to reverse, more dependencies, bigger blast radius, external commitments, strong opinions, long discussion
- **Higher number (less critical) if:** Purely internal, no user impact, preference rather than requirement

## Agreement Assessment

### Status Values

| Status | Criteria |
|--------|----------|
| **Agreed** | All parties explicitly agreed with clear evidence |
| **Needs Clarification** | Hedged agreement, terminology confusion, or implicit-only agreement |
| **Unresolved** | Topic parked, explicit disagreement, or no conclusion reached |

### Per-Person Agreement Values

| Value | Meaning | Evidence Required |
|-------|---------|-------------------|
| **Yes** | Explicitly agreed | "I agree", "I love that", "Let's do it", or proposed it |
| **Partial** | Agreed with qualifications | "Yes, to a degree", "I agree but...", "I can live with that" |
| **No** | Did not agree | Disagreed, silent, topic parked, moved on without confirming |

### Agreement Standards by Significance

**IMPORTANT: Be conservative. Default to "No" or "Partial" unless agreement is explicit.**

| Significance | Agreement Standard |
|--------------|-------------------|
| **1 - Critical** | ALL parties must explicitly acknowledge the exact decision. Any ambiguity = No |
| **2 - Extremely Important** | ALL parties must explicitly acknowledge. Any ambiguity = No |
| **3 - Important** | Explicit acknowledgment AND zero signs of hesitation. Any hint of misalignment = Partial or No |
| **4 - Moderate** | Clear alignment required; slight tolerance for ambiguity |
| **5 - Same Page** | General alignment sufficient. Only No/Partial if explicit disagreement |

### Conservative Assessment Rules

1. **Significance 1-2:** "Parking" = No, Silence = No, Moving on without confirmation = No
2. **Significance 3:** Different terminology, unanswered questions, or no explicit "we agree" = Partial or No
3. **One person declaring ≠ agreement.** Person B not confirming = No (Sig 1-2) or Partial (Sig 3-4)
4. **Hedged language:** "To a degree" = No (Sig 1-2), Partial (Sig 3-4), Yes (Sig 5)
5. **Topic resurfacing = false agreement**
6. **Confusion signals ("I'm confused", "wait, I thought...")** = NOT agreed

## Categories

| Category | Covers |
|----------|--------|
| **Go-to-Market** | Launch strategy, open source, market positioning, pricing |
| **Product Tiers** | Offline/single-player/multiplayer/enterprise modes, feature gating |
| **Technical Architecture** | Caching, data flow, server vs client, API design |
| **Data & Privacy** | Telemetry, privacy levels, data collection, retention |
| **Security** | Authentication, authorization, access control, secrets |
| **Terminology** | Naming conventions, taxonomy definitions, vocabulary |
| **Process** | Development workflow, deployment, team coordination |

## Types

| Type | Description |
|------|-------------|
| **Tech** | Technical implementation, architecture, tooling |
| **Legal** | Contracts, liability, terms of service, IP |
| **Compliance** | SOC 2, HIPAA, GDPR, regulatory requirements |
| **GTM** | Go-to-market, launch, distribution, partnerships |
| **Strategy** | Company direction, positioning, competitive |
| **Marketing** | Messaging, branding, content, campaigns |

## Output Format

### File Naming

```
meetings/YYYY-MM-DD/YYYY-MM-DD-Groundtruth.csv
meetings/YYYY-MM-DD/YYYY-MM-DD-Groundtruth.xlsx
```

### XLSX Formatting

**Significance Colors** (blue shades):
- 1: #0B5394 (Vibrant Blue, bold white text)
- 2: #3D85C6 (Strong Blue, bold white text)
- 3: #6FA8DC (Medium Blue)
- 4: #A4C2F4 (Light Blue)
- 5: #D9E6F7 (Near White)

**Status Colors**:
- Agreed: #C6EFCE (Light Green)
- Needs Clarification: #FFEB9C (Light Yellow)
- Unresolved: #FFC7CE (Light Red)

**Agreement Colors**:
- Yes: #C6EFCE (Green)
- Partial: #FFEB9C (Orange)
- No: #FFC7CE (Red, bold)

**Sorting:** Group by Category (alphabetically), then by Significance (1 first).

## See Also

- **[Decision Frameworks](decision-frameworks.md)** - Define who must agree on what for your team
- [Getting Started](getting-started.md) - Installation and first extraction
- [Configuration](configuration.md) - YAML config and LLM providers
- [Meeting Best Practices](meeting-best-practices.md) - Run better meetings
