# Meeting Best Practices

Groundtruth works best when meetings are run with decision-tracking in mind. A few simple habits dramatically improve extraction quality.

## State the Decision Framework Verbally

At the start of a meeting, have someone say who needs to agree on what. This gets captured in the transcript and guides extraction:

> "For this meeting, Steve and Martina need to agree on any GTM decisions, and Ajit and Ryan need to agree on technical architecture."

> "Today's decision-makers are Alice for product scope and Bob for timeline commitments."

## Be Explicit About Agreement

Instead of nodding or saying "sure," use clear language:

| Instead of... | Say... |
|---------------|--------|
| "Sure" | "I agree with that approach" |
| "Okay" | "Yes, let's do that" |
| "I guess" | "I can live with that, but I have concerns about X" |
| *silence* | "I'm not sure I agree—let's discuss" |

## Name Decisions When You Make Them

Help the tool (and your team) by explicitly calling out decisions:

> "So we're deciding to launch the beta in January. Everyone agree?"

> "Let me make sure I understand the decision: we're going with PostgreSQL, not MongoDB. Correct?"

## Park Items Explicitly

If you're tabling a discussion, say so clearly:

> "Let's park the pricing discussion for next week—we don't have enough data yet."

This gets marked as "Unresolved" rather than appearing as false agreement.

## State Your Role When Relevant

If decision authority matters, mention it:

> "As the engineering lead, I'm comfortable signing off on this technical approach."

> "I'll defer to Sarah on the legal implications since that's her area."

## Start with Last Meeting's Decisions

**Spend 5 minutes at the start of each meeting reviewing the previous meeting's Groundtruth output.** This:

- Reminds everyone what was decided
- Surfaces any decisions that need revisiting
- Catches false agreements early ("Wait, I didn't agree to that")
- Creates accountability for follow-through
- Closes the loop on "Unresolved" items

> "Before we start, let's review last week's decisions. We had 3 agreed items and 2 unresolved. Alice, you agreed to the PostgreSQL migration—still good? Bob, the pricing discussion was marked unresolved—do we have the data now?"

This simple habit transforms Groundtruth from a documentation tool into an alignment system.

---

## Quick Reference Checklist

**Before the meeting:**
- [ ] Review last meeting's Groundtruth output (5 min)
- [ ] Identify who the decision-makers are
- [ ] Prepare agenda with decision points
- [ ] Add any "Unresolved" items from last time

**During the meeting:**
- [ ] State decision framework at the start
- [ ] Name decisions explicitly when made
- [ ] Get explicit agreement from each person
- [ ] Park items clearly when tabling discussions

**After the meeting:**
- [ ] Run Groundtruth on transcript
- [ ] Review Significance 1-2 items
- [ ] Add Unresolved items to next agenda
- [ ] Share decisions with team

## Why This Matters

**Without explicit verbal cues:**
- LLMs can't distinguish agreement from silence
- "Sure" might mean enthusiasm or reluctant acceptance
- Moving to the next topic looks like consensus
- Important disagreements get lost

**With clear language:**
- Every decision has documented agreement
- Non-decisions are clearly marked
- Disagreements are captured, not hidden
- Team alignment improves dramatically

## See Also

- **[Decision Frameworks](decision-frameworks.md)** - Define who must agree on what for your team
- [Getting Started](getting-started.md) - Installation and first extraction
- [Configuration](configuration.md) - YAML config and LLM providers
- [Decision Tracking Guide](decision-tracking-guide.md) - Understanding significance and agreement
