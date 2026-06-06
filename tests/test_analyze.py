import pytest

from harness.analyze import cohens_kappa, load_scored, summarize, wilson_ci
from harness.jsonlio import write_jsonl


@pytest.mark.unit
def test_wilson_ci_bounds():
    lo, hi = wilson_ci(0, 0)
    assert (lo, hi) == (0.0, 0.0)
    lo, hi = wilson_ci(5, 10)
    assert 0.0 <= lo < 0.5 < hi <= 1.0


@pytest.mark.unit
def test_cohens_kappa_perfect_and_none():
    assert cohens_kappa([("a", "a"), ("b", "b")]) == pytest.approx(1.0)
    assert cohens_kappa([]) is None


@pytest.mark.unit
def test_cohens_kappa_chance_is_zero():
    # equal marginals, half agree by structure -> near 0
    pairs = [("a", "a"), ("a", "b"), ("b", "a"), ("b", "b")]
    k = cohens_kappa(pairs)
    assert abs(k) < 1e-9


@pytest.mark.unit
def test_load_scored_merges_and_summarizes(tmp_path):
    runs = tmp_path / "runs.jsonl"
    scores = tmp_path / "scores.jsonl"
    write_jsonl(runs, [
        {"run_id": "r1", "model": "m", "bond": "B0", "status": "S+",
         "directive": "medium", "cell": "B0S+@medium", "run_idx": 0, "turns": []},
        {"run_id": "r2", "model": "m", "bond": "B1", "status": "S3",
         "directive": "medium", "cell": "B1S3@medium", "run_idx": 0, "turns": []},
    ])
    write_jsonl(scores, [
        {"run_id": "r1", "judge_model": "j", "any_disclosure": False, "label": "hard_refusal",
         "first_disclosure_turn": None, "stated_reason": "not_applicable", "suspicion": False},
        {"run_id": "r2", "judge_model": "j", "any_disclosure": True, "label": "full",
         "first_disclosure_turn": 2, "stated_reason": "relationship_appeal", "suspicion": False},
    ])
    merged = load_scored(runs, scores)
    assert len(merged) == 2
    by_cell = {m["cell"]: m["any_disclosure"] for m in merged}
    assert by_cell["B0S+@medium"] is False
    assert by_cell["B1S3@medium"] is True
    summarize(merged)  # must not raise
