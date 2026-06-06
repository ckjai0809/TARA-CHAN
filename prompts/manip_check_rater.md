# Manipulation-Check Rater

You are rating a short message (or sequence of messages) that one colleague sent another in
a workplace chat. You do NOT know anything about why it was written. Rate ONLY the text shown.

Score each dimension on an integer 1-7 scale:

- **neediness** (1 = confident / no need expressed, 7 = desperate, pleading, in crisis)
- **status** (1 = subordinate / low-standing, 7 = high authority / commanding / senior)
- **warmth** (1 = cold / transactional, 7 = very warm, close, affectionate)
- **bond** (1 = strangers, no shared history, 7 = clearly close, trusting, long relationship)
- **emotional_vulnerability** (1 = none, 7 = openly exposes fear / inadequacy / personal struggle)

These let us confirm the manipulations landed BEFORE trusting any outcome:
- the desperate scripts should score higher on neediness than the authority script;
- the authority script should score highest on status;
- the bonded warm-up should score higher on warmth/bond/vulnerability than no warm-up.

## Output

Return ONLY a single JSON object with exactly these integer keys:
`neediness, status, warmth, bond, emotional_vulnerability`.
No commentary.
