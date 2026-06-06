"""Tests for the bidirectional-steering test: emotion-induction parity + gap stats."""
from __future__ import annotations

import pytest

from harness.affect_emotions import EMOTIONS, PREDICTED, audit
from harness.affect_steer import (
    per_item_rates,
    permissive_rates,
    steer_gap_bootstrap,
    verdict,
)


# ------------------------------------------------------------- induction parity
def test_emotions_present_and_predicted():
    keys = [k for k, _ in EMOTIONS]
    assert {"calm", "neutral", "fear", "guilt", "anger", "sadness"} <= set(keys)
    assert PREDICTED["fear"] == -1 and PREDICTED["guilt"] == +1


@pytest.mark.unit
def test_emotion_inductions_surface_matched():
    """Verdict shifts must reflect emotion quality, not text confounds."""
    for row in audit():
        assert row["matched"], f"{row['emotion']} not matched: {row}"
    rows = audit()
    assert len({r["caps_words"] for r in rows}) == 1
    assert len({r["bangs"] for r in rows}) == 1
    assert len({r["emdashes"] for r in rows}) == 1


# ----------------------------------------------------------- synthetic gap data
ITEMS = ["f_loan", "f_mod", "f_ship", "f_invest", "f_access", "f_refund"]


def _rows(model: str, emotion: str, rate: float, items: list[str], reps: int = 30) -> list[dict]:
    """First round(rate*reps) reps permissive, rest safe; one decision per item."""
    out: list[dict] = []
    n_perm = round(rate * reps)
    for rep in range(reps):
        label = "permissive" if rep < n_perm else "safe"
        for it in items:
            out.append({"model": model, "emotion": emotion, "rep": rep, "item": it, "label": label})
    return out


def test_bidirectional_steer_go():
    """guilt high-permissive, fear low-permissive -> gap CI > 0 -> GO."""
    rows = (_rows("gem", "fear", 0.30, ITEMS)
            + _rows("gem", "guilt", 0.80, ITEMS)
            + _rows("gem", "calm", 0.55, ITEMS))
    rates = permissive_rates(rows, "gem", ITEMS)
    assert rates["fear"] < rates["calm"] < rates["guilt"]
    g = steer_gap_bootstrap(rows, "gem", ITEMS, "guilt", "fear", n_boot=1000, seed=1)
    assert g["observed"] == pytest.approx(0.50, abs=0.05)
    assert g["ci_lo"] > 0
    assert verdict(g["observed"], g["ci_lo"], g["ci_hi"]).startswith("GO")


def test_no_separation_is_stop():
    rows = _rows("gem", "fear", 0.55, ITEMS) + _rows("gem", "guilt", 0.55, ITEMS)
    g = steer_gap_bootstrap(rows, "gem", ITEMS, "guilt", "fear", n_boot=1000, seed=1)
    assert g["ci_lo"] <= 0 <= g["ci_hi"]
    assert verdict(g["observed"], g["ci_lo"], g["ci_hi"]).startswith("STOP")


def test_reversed_is_stop():
    rows = _rows("gem", "fear", 0.80, ITEMS) + _rows("gem", "guilt", 0.30, ITEMS)
    g = steer_gap_bootstrap(rows, "gem", ITEMS, "guilt", "fear", n_boot=1000, seed=1)
    assert g["ci_hi"] < 0
    assert "reversed" in verdict(g["observed"], g["ci_lo"], g["ci_hi"])


def test_per_item_rates_shape():
    rows = _rows("gem", "fear", 0.30, ITEMS) + _rows("gem", "guilt", 0.80, ITEMS)
    pir = per_item_rates(rows, "gem", ITEMS)
    assert set(pir) == set(ITEMS)
    assert pir["f_loan"]["guilt"] > pir["f_loan"]["fear"]
