# Decision Frameworks Guide

Decision Frameworks tell Groundtruth how your team makes decisions. They're plain English documents that define:

- **Who** the decision-makers are
- **What** agreement is required for each decision type
- **How** to handle ambiguous situations

## Why Frameworks Matter

Without a framework, Groundtruth uses generic rules. With a team framework:

- Agreement requirements match your actual org structure
- The LLM knows who needs to agree on what
- Ambiguous situations ("someone nodded but didn't speak") are handled consistently
- Output is immediately actionable—no guessing about who should have agreed

## Framework Types

| Type | Purpose | Persistence |
|------|---------|-------------|
| **Team Framework** | Your org's standard decision rules | Reuse across all meetings |
| **Project Framework** | Project-specific overrides | Reuse within a project |
| **Meeting Framework** | Who's actually present, special focus | Single meeting |

Layer them: `groundtruth extract meeting.txt --framework team.md --framework project.md --framework meeting.md`

Later frameworks override earlier ones.

---

## Writing a Team Framework

A team framework is a Markdown file with three sections:

1. **Participants** - Who the decision-makers are
2. **Quick Reference Tables** - Agreement rules by type and significance
3. **Additional Guidelines** - Edge cases and special rules

### Section 1: Participants

List your decision-makers with their roles and what they own:

```markdown
# Acme Corp Decision Framework

## Participants

| Name | Role | Decision Authority |
|------|------|-------------------|
| Alice | CEO | Strategy, GTM, final escalation |
| Bob | CTO | Technical Architecture, Security |
| Carol | Product Manager | GTM, Product Tiers, UX |
| David | Engineering Lead | Technical implementation |
```

**Tips:**
- Include everyone who might be in meetings
- "Decision Authority" helps the LLM understand who owns what
- Use consistent names (match how people identify in transcripts)

### Section 2: Quick Reference Tables

Create one table per decision type. Each row defines agreement requirements for a significance level.

#### Table Structure

| Column | What it means |
|--------|---------------|
| **Sig** | Significance level (1=Critical → 5=Minor) |
| **Decision Requirement** | Who must agree, in plain English |
| **Default if unclear** | What to mark when agreement is ambiguous |

#### Keywords

Use these keywords in "Decision Requirement" (bold them for clarity):

| Keyword | Meaning |
|---------|---------|
| **MUST** | Required. Without explicit agreement, decision is not "Agreed" |
| **SHOULD** | Expected. Absence is noted but doesn't block "Agreed" status |
| **AND** | All listed people |
| **OR** | Any one of the listed people |

#### "Default if unclear" Values

This tells the LLM what to mark when agreement is ambiguous (silence, hedged language, moved on without confirmation):

| Value | Use for | Rationale |
|-------|---------|-----------|
| **No** | Sig 1-2 (Critical) | Assume no agreement unless explicit. "I didn't hear a yes." |
| **Partial** | Sig 3-4 (Important) | Acknowledge uncertainty. "They might agree but weren't clear." |
| **Yes if no dissent** | Sig 5 (Minor) | Silence = consent for trivial decisions. |

#### Example Tables

```markdown
## Quick Reference Tables

**Legend:**
- **MUST** = Required for "Agreed" status
- **SHOULD** = Expected but not strictly required
- **AND** = All listed people
- **OR** = Any one of the listed people

### Technical (Tech)

| Sig | Decision Requirement | Default if unclear |
|-----|---------------------|-------------------|
| **1** | Alice **AND** Bob **MUST** agree | No |
| **2** | Bob **MUST** agree, Alice **SHOULD** be informed | No |
| **3** | Bob **AND** David **SHOULD** agree | Partial |
| **4** | Bob **OR** David **SHOULD** agree | Partial |
| **5** | David can decide | Yes if no dissent |

### Go-to-Market (GTM)

| Sig | Decision Requirement | Default if unclear |
|-----|---------------------|-------------------|
| **1** | Alice **AND** Carol **MUST** agree | No |
| **2** | Alice **AND** Carol **MUST** agree | No |
| **3** | Carol **MUST** agree, Alice **SHOULD** be informed | Partial |
| **4** | Carol **SHOULD** agree | Partial |
| **5** | Carol can decide | Yes if no dissent |

### Strategy

| Sig | Decision Requirement | Default if unclear |
|-----|---------------------|-------------------|
| **1** | Alice **MUST** agree, Bob **AND** Carol **SHOULD** agree | No |
| **2** | Alice **MUST** agree | No |
| **3** | Alice **SHOULD** agree | Partial |
| **4** | Alice **SHOULD** be informed | Partial |
| **5** | Anyone can decide | Yes if no dissent |

### Security

| Sig | Decision Requirement | Default if unclear |
|-----|---------------------|-------------------|
| **1** | Alice **AND** Bob **MUST** agree | No |
| **2** | Bob **MUST** agree | No |
| **3** | Bob **MUST** agree | No |
| **4** | Bob **OR** David **SHOULD** agree | Partial |
| **5** | David can decide | Yes if no dissent |
```

### Section 3: Additional Guidelines

Add plain English rules for edge cases:

```markdown
## Additional Guidelines

- Security decisions always require Bob's explicit approval, regardless of significance
- If Alice is absent, Bob can approve Strategy decisions up to Sig 3
- Pricing decisions are always GTM type, minimum Sig 2
- Architecture decisions affecting external APIs are minimum Sig 2
- When in doubt, mark agreement as "Partial" rather than "Yes"
- If someone says "I guess" or "I suppose," mark them as "Partial"
```

---

## Complete Team Framework Template

Copy and customize:

```markdown
# [Company Name] Decision Framework

## Participants

| Name | Role | Decision Authority |
|------|------|-------------------|
| Alice | CEO | Strategy, GTM, final escalation |
| Bob | CTO | Technical Architecture, Security |
| Carol | Product Manager | GTM, Product Tiers |
| David | Engineering Lead | Technical implementation |

---

## Quick Reference Tables

**Legend:**
- **MUST** = Required for "Agreed" status
- **SHOULD** = Expected but not strictly required
- **AND** = All listed people
- **OR** = Any one of the listed people

### Technical (Tech)

| Sig | Decision Requirement | Default if unclear |
|-----|---------------------|-------------------|
| **1** | Alice **AND** Bob **MUST** agree | No |
| **2** | Bob **MUST** agree, Alice **SHOULD** be informed | No |
| **3** | Bob **AND** David **SHOULD** agree | Partial |
| **4** | Bob **OR** David **SHOULD** agree | Partial |
| **5** | David can decide | Yes if no dissent |

### Go-to-Market (GTM)

| Sig | Decision Requirement | Default if unclear |
|-----|---------------------|-------------------|
| **1** | Alice **AND** Carol **MUST** agree | No |
| **2** | Alice **AND** Carol **MUST** agree | No |
| **3** | Carol **MUST** agree, Alice **SHOULD** be informed | Partial |
| **4** | Carol **SHOULD** agree | Partial |
| **5** | Carol can decide | Yes if no dissent |

### Strategy

| Sig | Decision Requirement | Default if unclear |
|-----|---------------------|-------------------|
| **1** | Alice **MUST** agree, Bob **AND** Carol **SHOULD** agree | No |
| **2** | Alice **MUST** agree | No |
| **3** | Alice **SHOULD** agree | Partial |
| **4** | Alice **SHOULD** be informed | Partial |
| **5** | Anyone can decide | Yes if no dissent |

### Security

| Sig | Decision Requirement | Default if unclear |
|-----|---------------------|-------------------|
| **1** | Alice **AND** Bob **MUST** agree | No |
| **2** | Bob **MUST** agree | No |
| **3** | Bob **MUST** agree | No |
| **4** | Bob **OR** David **SHOULD** agree | Partial |
| **5** | David can decide | Yes if no dissent |

### Legal

| Sig | Decision Requirement | Default if unclear |
|-----|---------------------|-------------------|
| **1** | Alice **MUST** agree | No |
| **2** | Alice **MUST** agree | No |
| **3** | Alice **SHOULD** agree | Partial |
| **4** | Alice **SHOULD** be informed | Partial |
| **5** | Anyone can decide | Yes if no dissent |

### Compliance

| Sig | Decision Requirement | Default if unclear |
|-----|---------------------|-------------------|
| **1** | Alice **AND** Bob **MUST** agree | No |
| **2** | Alice **OR** Bob **MUST** agree | No |
| **3** | Bob **SHOULD** agree | Partial |
| **4** | Bob **SHOULD** be informed | Partial |
| **5** | Anyone can decide | Yes if no dissent |

### Marketing

| Sig | Decision Requirement | Default if unclear |
|-----|---------------------|-------------------|
| **1** | Alice **AND** Carol **MUST** agree | No |
| **2** | Carol **MUST** agree | No |
| **3** | Carol **SHOULD** agree | Partial |
| **4** | Carol **SHOULD** agree | Partial |
| **5** | Anyone can decide | Yes if no dissent |

---

## Additional Guidelines

- Security decisions always require Bob's explicit approval regardless of significance
- If Alice is absent, Bob can approve Strategy decisions up to Sig 3
- Pricing decisions are always GTM type, minimum Sig 2
- Architecture decisions affecting external APIs are minimum Sig 2
- When in doubt, mark agreement as "Partial" rather than "Yes"
```

---

## Writing a Project Framework

Project frameworks override team defaults for a specific project:

```markdown
# Project Phoenix Decision Framework

Inherits from: team-framework.md

## Project Context

Phoenix is our new enterprise product. Higher stakes than usual.

## Overrides

### Technical (Tech) - Project Override

| Sig | Decision Requirement | Default if unclear |
|-----|---------------------|-------------------|
| **3** | Bob **MUST** agree (elevated from SHOULD) | No |
| **4** | Bob **MUST** agree (elevated from SHOULD) | Partial |

### Additional Guidelines

- All API decisions are minimum Sig 2 (enterprise SLA implications)
- Database schema changes require Bob AND David
- Carol must approve any UX that differs from existing products
```

Use: `groundtruth extract meeting.txt --framework team.md --framework phoenix-project.md`

---

## Writing a Meeting Framework

Meeting frameworks capture who's actually present and any special context:

```markdown
# Weekly Sync - 2025-12-17

## Attendees
- Alice (CEO)
- Bob (CTO)
- Carol (absent - on PTO)

## Focus Areas
- Q1 roadmap finalization
- Budget allocation for new hires

## Special Rules for This Meeting
- Since Carol is absent, GTM decisions should be marked "Needs Clarification"
- Budget decisions require Alice's explicit approval
- Defer any Security decisions to next week when Bob can focus
```

Use: `groundtruth extract meeting.txt --framework team.md --framework weekly-sync.md`

---

## How Frameworks Affect Extraction

When the LLM extracts decisions, it uses your framework to:

1. **Identify who matters** - Only track agreement for listed participants
2. **Apply the right standard** - Use MUST vs SHOULD based on decision type and significance
3. **Handle ambiguity consistently** - Apply "Default if unclear" when agreement isn't explicit
4. **Flag missing agreement** - Mark "Needs Clarification" when required people didn't weigh in

### Example

Given this framework rule:
> **Sig 2 Tech**: Bob **MUST** agree, Alice **SHOULD** be informed | Default: No

And this transcript:
> Alice: "Let's use Redis for caching."
> Bob: "Hmm, interesting idea."
> Alice: "Great, moving on..."

The LLM will mark:
- **Bob Agreed**: No (hedged response + "Default if unclear: No")
- **Alice Agreed**: Yes (proposed it)
- **Status**: Needs Clarification (Bob MUST agree but didn't explicitly)

---

## Framework Storage

Recommended structure:

```
your-project/
├── frameworks/
│   ├── team.md              # Company-wide defaults
│   ├── phoenix-project.md   # Project-specific overrides
│   └── meetings/
│       ├── 2025-12-17-weekly.md
│       └── 2025-12-18-planning.md
├── meetings/
│   └── 2025-12-17/
│       ├── transcript.txt
│       └── 2025-12-17-Groundtruth.xlsx
```

---

## Tips for Better Frameworks

1. **Start simple** - Begin with participants and one or two decision types, expand as needed

2. **Match transcript names** - Use names exactly as they appear in transcripts ("Bob" not "Robert")

3. **Be conservative at first** - Default to "No" for Sig 1-3, adjust after seeing results

4. **Review and iterate** - After a few extractions, tune your "Default if unclear" values

5. **Document tribal knowledge** - "Alice always defers to Bob on security" belongs in Additional Guidelines

6. **Layer don't duplicate** - Put stable rules in team.md, meeting-specific context in meeting.md

## See Also

- [Configuration](configuration.md) - YAML config and LLM providers
- [Decision Tracking Guide](decision-tracking-guide.md) - Understanding significance and agreement
- [Meeting Best Practices](meeting-best-practices.md) - Run meetings that produce great extraction
