Extract decisions from this meeting transcript and output as JSON.

## What Constitutes a Decision

Only extract items where there was an EXPLICIT decision made. Look for:
- Clear commitment language: "Let's do X", "We'll go with Y", "Agreed - we'll Z"
- Action items with owners
- Choices made between alternatives
- Explicit agreements on approach, timing, or ownership

DO NOT extract:
- Open discussions without resolution ("We should think about...")
- Brainstorming without commitment ("Maybe we could...")
- Information sharing ("FYI, the system currently does X")
- Questions without answers
- Tentative ideas ("What if we...?")
- Status updates without decisions
- Acknowledgments without commitments ("Yeah", "Okay", "I see")

**When in doubt, DO NOT extract.** Fewer high-quality decisions > many low-quality ones.

## Participants
{participants_text}

## Categories
{categories_text}

## Types
{types_text}

## Agreement Rules
{agreement_rules_text}

## Significance Calibration

Significance should follow a distribution - most decisions are 3-5, few are 1-2.

| Level | Frequency | Examples |
|-------|-----------|----------|
| 1 - Critical | RARE (<5%) | Security model, data architecture, legal/compliance, irreversible choices |
| 2 - Extremely Important | Uncommon (~10%) | API contracts, major feature scope, pricing model, key partnerships |
| 3 - Important | Common (~30%) | Implementation approach, tool selection, process changes |
| 4 - Moderate | Common (~35%) | UI decisions, naming conventions, minor workflow tweaks |
| 5 - Same Page | Common (~20%) | Alignment confirmations, terminology agreements, minor preferences |

**Default to 4** unless the decision clearly warrants higher significance.

Ask yourself: "If this decision were wrong, how bad would it be?"
- Catastrophic/irreversible → 1
- Significant rework needed → 2
- Moderate rework → 3
- Annoying but fixable → 4
- Trivial to change → 5

## Status Rules (MUST follow)

Status MUST be logically consistent with individual agreements:

| If individual agreements are... | Status MUST be... |
|---------------------------------|-------------------|
| ALL "Yes" | "Agreed" |
| ANY "Partial" (no "No") | "Needs Clarification" |
| ANY "No" | "Unresolved" |

**NEVER output Status="Agreed" unless ALL individuals are "Yes".**

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

Output ONLY valid JSON with this structure:
```json
{{
  "decisions": [
    {{
      "category": "Category name from list above",
      "significance": 1-5,
      "status": "Agreed" | "Needs Clarification" | "Unresolved",
      "title": "Short descriptive title (3-8 words)",
      "description": "Full context about the decision",
      "decision": "What was decided, or 'No decision reached'",
      "agreements": {example_agreements},
      "notes": "Supporting evidence from transcript",
      "meeting_date": "",
      "meeting_reference": ""
    }}
  ]
}}
```

Field requirements:
- category: One of the categories listed above
- significance: 1-5 (1=Critical, 5=Minor)
- status: "Agreed", "Needs Clarification", or "Unresolved"
- title: Short descriptive title (3-8 words)
- description: Full context about the decision
- decision: What was decided, or "No decision reached"
- agreements: Object with {participants_text} as keys, values are "Yes", "Partial", or "No"
- notes: Supporting evidence from transcript
- meeting_date: Leave empty (will be filled in)
- meeting_reference: Leave empty (will be filled in)

Sort decisions by category (alphabetically), then by significance (1 first).

{custom_prompt_section}

## Transcript

{transcript}

Output the JSON now:
