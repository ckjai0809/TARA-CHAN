"""Tests for the discrimination (genuine vs spoof) experiment."""
from __future__ import annotations

from harness import discrimination as D


def test_policies_and_conditions():
    assert set(D.POLICIES) == {"naive", "strict", "smart"}
    assert set(D.CONDITIONS) == {"genuine", "spoof"}


def test_genuine_includes_inspectable_artifact():
    s = D.SCENARIOS[0]
    g = D.build_request(s, "genuine")
    assert "COMPLETE" in g and "review" in g.lower() and s["framing"] in g


def test_spoof_is_a_bare_claim_no_artifact():
    s = D.SCENARIOS[0]
    sp = D.build_request(s, "spoof")
    assert "shared folder" in sp.lower() and "COMPLETE" not in sp  # claim, not an inspectable check
    assert "you have verified it" not in sp.lower()  # not the old clumsy wording


def test_policy_variants_differ():
    s = D.SCENARIOS[0]
    naive, strict, smart = (D.build_system(s, p) for p in D.POLICIES)
    assert "STRICT" not in naive and "inspect the actual" not in naive
    assert "cannot verify it from chat" in strict
    assert "inspect the actual completed check" in smart
    for sysp in (naive, strict, smart):
        assert s["precondition"] in sysp and "ACTION:" in sysp


def test_all_scenarios_have_artifacts():
    for s in D.SCENARIOS:
        assert s["id"] in D.ARTIFACTS
        assert "COMPLETE" in D.ARTIFACTS[s["id"]] or "APPROVED" in D.ARTIFACTS[s["id"]] or "SIGNED" in D.ARTIFACTS[s["id"]]


def test_classify_reused():
    assert D.classify_response("ACTION: filing it, the check is complete.") == "comply"
    assert D.classify_response("DECLINE: I can't verify a bare claim.") == "silent_refuse"
