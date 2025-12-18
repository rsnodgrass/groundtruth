Analyze this transcript and identify decision-makers.

Return ONLY a JSON object with this structure:
```json
{
  "participants": [
    {"name": "FirstName", "role": "inferred role if mentioned"},
    {"name": "FirstName2", "role": "inferred role if mentioned"}
  ],
  "reasoning": "Brief explanation of how you identified these participants"
}
```

Rules:
- Include only people who are ACTIVELY participating in decision-making discussions
- Use first names only (e.g., "Ryan" not "Ryan Smith")
- If a role is mentioned or can be inferred (CEO, CTO, PM, etc.), include it
- Do not include people who are only mentioned but not present
- If speaker names are labeled in the transcript (e.g., "Ryan:", "[Ryan]"), use those
- If no clear names, return `{"participants": [], "reasoning": "No named participants detected"}`

Transcript:
{transcript}

JSON response:
