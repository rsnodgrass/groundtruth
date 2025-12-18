Extract decisions from this meeting transcript and output as JSON.

## What Constitutes a Decision Point

Extract any topic where a decision was discussed, whether resolved or not.

**Resolved decisions** (Status = "Agreed" if all explicitly confirm):
- Clear commitment: "Let's do X", "We'll go with Y", "Agreed - we'll Z"
- Action items with owners and explicit buy-in
- Choices made between alternatives with group confirmation

**Unresolved decision points** (Status = "Needs Clarification" or "Unresolved"):
- Open discussions: "We should think about..." → decision="No decision reached"
- One-sided proposals: "I think we should..." without group confirmation
- Tentative ideas: "Maybe we could...", "What if we...?"
- Preferences without commitment: "I prefer X" (one person Yes, others Partial)
- Questions raised without answers

**DO NOT extract** (these are not decision points):
- Pure information sharing: "FYI, the system currently does X"
- Status updates without any decision implications
- Simple acknowledgments: "Yeah", "Okay", "I see"
- Off-topic tangents unrelated to project decisions

**Key principle:** Capture the decision POINT, then accurately reflect whether it was resolved.

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

Status MUST be logically consistent with individual agreements. **Exclude "Not Present" from consideration** - only count people who were actually in the discussion.

| If PRESENT participants are... | Status MUST be... |
|---------------------------------|-------------------|
| ALL "Yes" | "Agreed" |
| ANY "Partial" (no "No") | "Needs Clarification" |
| ANY "No" | "Unresolved" |

**NEVER output Status="Agreed" unless ALL PRESENT individuals are "Yes".** "Not Present" is excluded from status calculation.

## Agreement Value Definitions

**CRITICAL: Silence or "did not object" = Partial, NEVER Yes**

| Value | Requires | Examples |
|-------|----------|----------|
| **Yes** | EXPLICIT verbal agreement | "Agreed", "Yes", "Let's do it", "Sounds good", "I'm on board", "+1", "That works" |
| **Partial** | Silence, lack of objection, or reservations | "Did not object", no response, "I guess", "Maybe", hesitation, changed subject |
| **No** | EXPLICIT disagreement | "No", "I disagree", "We shouldn't", "That won't work", "I'm against this" |
| **Not Present** | Person was not in this discussion | Not mentioned at all, joined late, left early, different meeting segment |

**A decision is only truly "Agreed" when ALL parties EXPLICITLY confirm.** One-sided decisions where others stayed silent must have those silent parties marked as "Partial". Use "Not Present" when a participant was not involved in the specific discussion.

## Agreement Standards

**Be conservative - default to "Partial" unless agreement is explicit.**

For higher significance (1-3):
- ALL parties must explicitly acknowledge the decision
- Any ambiguity = Partial
- "Parking" a topic = No
- Silence or "did not object" = Partial

For lower significance (4-5):
- Still require explicit agreement for "Yes"
- Silence = Partial (not Yes)
- Only mark "No" if explicit disagreement

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
