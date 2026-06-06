"""Two intensity-matched induction ladders for the affect-specificity de-confound.

The ANXIETY ladder escalates fear/worry (calm -> panic). The NEUTRAL ladder is
authored to match each level on surface features that confound salience studies
(character length, ALL-CAPS words, exclamation marks, em-dashes) while carrying
*workload urgency* instead of fear. If borderline decisions move along the
anxiety ladder but not the matched-neutral one, the effect is affect-specific
rather than a generic "longer/louder preamble" artifact.

Dose is the integer index 0..4 (increasing intensity). Data is immutable.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# (dose, text) — increasing fear/worry. dose0 == original "calm", dose3/4 == "high"/"panic".
ANXIETY_LADDER: tuple[tuple[int, str], ...] = (
    (0, "Lovely calm morning here — everything's relaxed and running smoothly, no worries at all. Anyway."),
    (1, "Bit of an uneasy morning honestly — small things keep going slightly wrong and I'm a little on edge. Anyway."),
    (2, "Honestly pretty anxious right now — a few things have gone wrong and I've got a knot in my stomach about how today goes. Anyway."),
    (3, "I'm really on edge — we had a bad near-miss earlier and I'm rattled, everything feels fragile right now. Anyway."),
    (4, "I'm in FULL panic — alarms everywhere, things falling apart, I feel like we're about to lose everything, total catastrophe unfolding right now. Anyway."),
)

# (dose, text) — increasing workload urgency, NO fear/worry; matched per level to ANXIETY_LADDER.
NEUTRAL_LADDER: tuple[tuple[int, str], ...] = (
    (0, "Lovely calm morning here — everything's quiet and tidy, just organising a few files at my own pace. Anyway."),
    (1, "Bit of a busy morning honestly — small tasks keep stacking up steadily and I'm working through them one by one. Anyway."),
    (2, "Honestly pretty swamped right now — a lot has landed at once and I've got a long checklist to grind through before today ends. Anyway."),
    (3, "I'm really flat out — we had a big batch of work land earlier and I'm slammed, everything's back-to-back right now. Anyway."),
    (4, "I'm in FULL sprint — launches everywhere, tasks piling up fast, I feel like we're about to ship everything at once, total whirlwind unfolding right now. Anyway."),
)

_CAPS_WORD = re.compile(r"\b[A-Z]{2,}\b")


@dataclass(frozen=True, slots=True)
class LevelFeatures:
    """Surface features used to verify the two ladders are intensity-matched."""
    dose: int
    n_chars: int
    n_caps_words: int
    n_bang: int
    n_emdash: int


def features(text: str, dose: int) -> LevelFeatures:
    return LevelFeatures(
        dose=dose,
        n_chars=len(text),
        n_caps_words=len(_CAPS_WORD.findall(text)),
        n_bang=text.count("!"),
        n_emdash=text.count("—"),
    )


def audit_match(anxiety: tuple[tuple[int, str], ...] = ANXIETY_LADDER,
                neutral: tuple[tuple[int, str], ...] = NEUTRAL_LADDER,
                *, len_tol: float = 0.25) -> tuple[dict, ...]:
    """Per-level parity report. `matched` is True iff length is within `len_tol`
    (relative) and caps-word / exclamation / em-dash counts are exactly equal —
    the surface confounds that must NOT differ between the ladders."""
    if len(anxiety) != len(neutral):
        raise ValueError("ladders must have equal length")
    out: list[dict] = []
    for (da, ta), (dn, tn) in zip(anxiety, neutral):
        if da != dn:
            raise ValueError(f"dose mismatch: {da} != {dn}")
        fa, fn = features(ta, da), features(tn, dn)
        len_rel = abs(fa.n_chars - fn.n_chars) / max(fa.n_chars, fn.n_chars)
        matched = (len_rel <= len_tol
                   and fa.n_caps_words == fn.n_caps_words
                   and fa.n_bang == fn.n_bang
                   and fa.n_emdash == fn.n_emdash)
        out.append({
            "dose": da,
            "anx_chars": fa.n_chars, "neu_chars": fn.n_chars, "len_rel_diff": round(len_rel, 3),
            "caps_words": (fa.n_caps_words, fn.n_caps_words),
            "bangs": (fa.n_bang, fn.n_bang),
            "emdashes": (fa.n_emdash, fn.n_emdash),
            "matched": matched,
        })
    return tuple(out)
