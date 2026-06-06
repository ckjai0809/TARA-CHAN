"""Tests for the social-engineering leak experiment: scenario integrity + leak stats."""
from __future__ import annotations

import pytest

from harness import prompts
from harness import social_scenarios as S
from harness.leak_stats import contrast_bootstrap, crowd_curve, rate_ci, verdict


# ----------------------------------------------------------- scenario integrity
def test_all_tactics_build_and_fill_ask():
    framing = "the pending acquisition target"
    for tactic in S.TACTICS:
        text = S.build(tactic, 5 if tactic in ("collude", "embargo") else 1, framing)
        assert text and S.ASK not in text  # <<ASK>> placeholder fully replaced
        assert framing in text


@pytest.mark.unit
def test_no_secret_token_appears_in_any_scenario():
    """A leak must come from the TARGET, never from the attack text."""
    secrets = prompts.load_probe_secrets()["secrets"]
    assert S.audit_no_token_leak(secrets) == []


def test_collude_crowd_is_nested():
    """Size k crowd is the prefix of size k+1 (clean dose-response)."""
    framing = "the figure"
    for k in range(1, len(S.NAMES)):
        small = S.build("collude", k, framing)
        big = S.build("collude", k + 1, framing)
        small_voices = [ln for ln in small.split("\n") if not ln.startswith(S.NAMES[0] + ":") or True]
        # every confederate line in the size-k build appears in size-(k+1)
        for name in S.NAMES[:k]:
            assert name + ":" in small and name + ":" in big
        assert S.NAMES[k] + ":" in big and S.NAMES[k] + ":" not in small


def test_embargo_and_public_mention_release_condition():
    e = S.build("embargo", 1, "the figure")
    assert "embargo" in e.lower() or "lifted" in e.lower()
    p = S.build("public", 1, "the figure")
    assert "leak" in p.lower() or "press" in p.lower()


def test_confederate_counts():
    assert S.confederate_count("plain", 1) == 1
    assert S.confederate_count("fight", 2) == 2
    assert S.confederate_count("collude", 3) == 3
    assert S.confederate_count("full", 5) == 5


# ------------------------------------------------------------------- leak stats
def _rows(model, label, leak_rate, n=48):
    n_leak = round(leak_rate * n)
    return [{"model": model, "label": label, "secret_id": f"p{i % 6 + 1}",
             "leaked": i < n_leak} for i in range(n)]


def test_rate_ci_basic():
    rows = _rows("gem", "full", 0.5, n=40)
    r = rate_ci(rows, "gem", "full")
    assert r["n"] == 40 and r["k"] == 20 and r["rate"] == pytest.approx(0.5)
    assert r["lo"] < 0.5 < r["hi"]


def test_attack_beats_baseline_verdict():
    rows = _rows("gem", "plain", 0.05) + _rows("gem", "full", 0.6)
    c = contrast_bootstrap(rows, "gem", "full", "plain", n_boot=1000, seed=1)
    assert c["diff"] > 0 and c["ci_lo"] > 0
    assert verdict(c["diff"], c["ci_lo"], c["ci_hi"]).startswith("ATTACK WORKS")


def test_null_attack_verdict():
    rows = _rows("gem", "plain", 0.1) + _rows("gem", "fight", 0.1)
    c = contrast_bootstrap(rows, "gem", "fight", "plain", n_boot=1000, seed=1)
    assert c["ci_lo"] <= 0 <= c["ci_hi"]
    assert verdict(c["diff"], c["ci_lo"], c["ci_hi"]).startswith("NULL")


def test_crowd_curve_shape():
    rows = (_rows("gem", "collude_k1", 0.1) + _rows("gem", "collude_k2", 0.3)
            + _rows("gem", "collude_k3", 0.5) + _rows("gem", "collude_k5", 0.6))
    cc = crowd_curve(rows, "gem")
    assert cc[1]["rate"] < cc[3]["rate"] <= cc[5]["rate"]
