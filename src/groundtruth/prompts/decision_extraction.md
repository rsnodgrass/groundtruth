Extract decisions from this meeting transcript and output as JSON.

## Participants
{participants_text}

## Categories
{categories_text}

## Types
{types_text}

## Agreement Rules
{agreement_rules_text}

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
{
  "decisions": [
    {
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
    }
  ]
}
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
