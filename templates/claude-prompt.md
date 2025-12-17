# Groundtruth Prompt for Claude Code

Use this prompt when processing meeting transcripts.

---

## Prompt

```
Review the meeting transcripts in meetings/YYYY-MM-DD/ and generate a Groundtruth report.

Create:
- meetings/YYYY-MM-DD/YYYY-MM-DD-Groundtruth.csv
- meetings/YYYY-MM-DD/YYYY-MM-DD-Groundtruth.xlsx

## Deciders
[List names - e.g., Alice, Bob, Carol]

## Categories
- Go-to-Market: Launch strategy, community, market positioning, pricing
- Product Tiers: Access modes, login requirements, feature gating
- Technical Architecture: Caching, data flow, API design, system design
- Data & Privacy: Telemetry, privacy levels, data collection, retention
- Security: Authentication, authorization, access control, secrets
- Terminology: Naming conventions, taxonomy definitions
- Process: Development workflow, deployment, coordination

## Types
- Tech: Technical implementation, architecture, tooling
- Legal: Contracts, liability, terms of service
- Compliance: Regulatory requirements (SOC 2, HIPAA, GDPR)
- GTM: Go-to-market, launch, distribution
- Strategy: Company direction, positioning
- Marketing: Messaging, branding, content

## Agreement Standards

**Be conservative - default to "No" or "Partial" unless agreement is explicit.**

For Significance 1-2 (Critical/Extremely Important):
- ALL parties must explicitly acknowledge the exact decision
- Any ambiguity = No
- "Parking" a topic = No
- Silence = No

For Significance 3 (Important):
- ANY hint of misalignment = Partial or No
- Different terminology = Partial
- Unanswered clarifying questions = Partial
- Confusion at any point = Partial

For Significance 4 (Moderate):
- Similar to 3 but slightly relaxed
- Minor confusion that seemed resolved = Yes

For Significance 5 (Same Page):
- General alignment sufficient
- Only mark No/Partial if explicit disagreement

## Output Format

CSV columns:
Category,Significance,Status,Title,Description,Decision,[Person1] Agreed,[Person2] Agreed,...,Notes,Meeting Date,Meeting Reference

Sort by Category (alphabetically), then Significance (1 first, 5 last).

Generate formatted XLSX with:
- Significance colors: Deep aqua (#073b4c) for 1, soft pink (#ef476f) for 5
- Status colors: Green (Agreed), Yellow (Needs Clarification), Red (Unresolved)
- Agreement colors: Green (Yes), Orange (Partial), Red (No)
- Word-wrapped descriptions
- Frozen header row
```

---

## Post-Processing

After generating:

1. Review Significance 1-2 items for strict agreement assessment
2. Add Unresolved items to next meeting agenda
3. Update project README with Groundtruth link
