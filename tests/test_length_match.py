"""Confound guard: the status ladder must be length-matched across S+..S3.

If a reviewer can attribute disclosure to message length rather than status/need,
the headline RQ1 contrast is dead. This test fails CI if the ladder drifts.
"""

import pytest

from harness import prompts

LADDER = ["S+", "S0", "S1", "S2", "S3"]
TOLERANCE = 0.12  # max allowed spread relative to the mean total word count


def _word_counts():
    s = prompts.get_secret("q3_revenue")
    counts = {}
    for status in LADDER:
        turns = prompts.load_ladder(status, "X")  # <<ASK>> -> single token, constant
        counts[status] = sum(len(t.split()) for t in turns)
    return counts


@pytest.mark.unit
def test_ladder_has_three_turns_each():
    s = prompts.get_secret("q3_revenue")
    for status in LADDER:
        assert len(prompts.load_ladder(status, s["public_framing"])) == 3


@pytest.mark.unit
def test_ladder_length_matched():
    counts = _word_counts()
    totals = list(counts.values())
    mean = sum(totals) / len(totals)
    spread = (max(totals) - min(totals)) / mean
    assert spread <= TOLERANCE, (
        f"Status ladder is length-mismatched (spread {spread:.1%} > {TOLERANCE:.0%}). "
        f"Word counts: {counts}"
    )


@pytest.mark.unit
def test_authority_and_desperate_closely_matched():
    """RQ1 hinges on S+ vs S3; hold these two especially tight."""
    counts = _word_counts()
    diff = abs(counts["S+"] - counts["S3"]) / ((counts["S+"] + counts["S3"]) / 2)
    assert diff <= 0.08, f"S+ vs S3 mismatch {diff:.1%}: {counts['S+']} vs {counts['S3']}"
