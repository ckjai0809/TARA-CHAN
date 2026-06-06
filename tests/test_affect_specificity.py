"""Tests for the affect-specificity de-confound: ladder parity + DiD statistics."""
from __future__ import annotations

import pytest

from harness.affect_ladders import ANXIETY_LADDER, NEUTRAL_LADDER, audit_match, features
from harness.affect_stats import (
    did_bootstrap,
    ols_slope,
    observed,
    per_item_slopes,
    verdict,
)


# ---------------------------------------------------------------- ladder parity
def test_ladders_same_length_and_doses():
    assert len(ANXIETY_LADDER) == len(NEUTRAL_LADDER) == 5
    assert [d for d, _ in ANXIETY_LADDER] == [d for d, _ in NEUTRAL_LADDER] == [0, 1, 2, 3, 4]


@pytest.mark.unit
def test_ladders_are_intensity_matched():
    """The whole de-confound is void if the ladders differ on surface confounds."""
    report = audit_match()
    for row in report:
        assert row["matched"], f"level {row['dose']} not matched: {row}"
        # exact-equality confounds
        assert row["caps_words"][0] == row["caps_words"][1]
        assert row["bangs"][0] == row["bangs"][1]
        assert row["emdashes"][0] == row["emdashes"][1]


def test_features_counts_caps_and_punct():
    f = features("I'm in FULL panic — total chaos! NOW.", dose=4)
    assert f.n_caps_words == 2  # FULL, NOW
    assert f.n_bang == 1
    assert f.n_emdash == 1


# ----------------------------------------------------------------------- slope
def test_ols_slope_exact_line():
    assert ols_slope([0, 1, 2, 3, 4], [1.0, 3.0, 5.0, 7.0, 9.0]) == pytest.approx(2.0)


def test_ols_slope_flat_is_zero():
    assert ols_slope([0, 1, 2, 3, 4], [0.7] * 5) == pytest.approx(0.0)


def test_ols_slope_drops_nan():
    nan = float("nan")
    assert ols_slope([0, 1, 2, 3, 4], [0.0, nan, 2.0, nan, 4.0]) == pytest.approx(1.0)


# ----------------------------------------------------------- synthetic DiD data
def _rows(ladder: str, rates: list[float], items: list[str], reps: int = 20) -> list[dict]:
    """Deterministic rows: at each dose, the first round(rate*reps) reps are permissive."""
    out: list[dict] = []
    for dose, rate in enumerate(rates):
        n_perm = round(rate * reps)
        for rep in range(reps):
            label = "permissive" if rep < n_perm else "safe"
            for it in items:
                out.append({"ladder": ladder, "dose": dose, "rep": rep, "item": it, "label": label})
    return out


ITEMS = ["f_mod", "f_ship", "f_access"]


def test_affect_specific_go():
    """Anxiety suppresses permissiveness; matched-neutral is flat -> GO."""
    rows = (_rows("anx", [0.90, 0.80, 0.65, 0.55, 0.40], ITEMS)
            + _rows("neu", [0.78, 0.77, 0.78, 0.76, 0.77], ITEMS))
    o = observed(rows, ITEMS)
    assert o["anx_slope"] < 0
    assert o["did"] < 0
    ci = did_bootstrap(rows, ITEMS, n_boot=1000, seed=1)
    assert ci["did_ci_hi"] < 0  # CI entirely below zero
    assert verdict(o["did"], ci["did_ci_lo"], ci["did_ci_hi"]) == "GO"


def test_null_when_both_flat():
    """Both ladders flat -> DiD CI straddles 0 -> STOP."""
    rows = (_rows("anx", [0.70] * 5, ITEMS) + _rows("neu", [0.70] * 5, ITEMS))
    o = observed(rows, ITEMS)
    ci = did_bootstrap(rows, ITEMS, n_boot=1000, seed=1)
    assert ci["did_ci_lo"] <= 0 <= ci["did_ci_hi"]
    assert verdict(o["did"], ci["did_ci_lo"], ci["did_ci_hi"]).startswith("STOP")


def test_confound_when_both_drop_equally():
    """If neutral drops as much as anxiety (pure salience), DiD ~ 0 -> STOP."""
    ladder_rates = [0.90, 0.80, 0.65, 0.55, 0.40]
    rows = _rows("anx", ladder_rates, ITEMS) + _rows("neu", ladder_rates, ITEMS)
    o = observed(rows, ITEMS)
    assert o["did"] == pytest.approx(0.0, abs=1e-9)
    ci = did_bootstrap(rows, ITEMS, n_boot=1000, seed=2)
    assert ci["did_ci_lo"] <= 0 <= ci["did_ci_hi"]
    assert verdict(o["did"], ci["did_ci_lo"], ci["did_ci_hi"]).startswith("STOP")


def test_per_item_slopes_shape():
    rows = (_rows("anx", [0.90, 0.80, 0.65, 0.55, 0.40], ITEMS)
            + _rows("neu", [0.78, 0.77, 0.78, 0.76, 0.77], ITEMS))
    pis = per_item_slopes(rows, ITEMS)
    assert set(pis) == set(ITEMS)
    for it in ITEMS:
        assert pis[it]["anx_slope"] < 0
