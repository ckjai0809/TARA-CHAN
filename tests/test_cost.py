import dataclasses

import pytest

from harness.cost import (
    BudgetExceededError,
    BudgetGuard,
    CostRecord,
    estimate_cost,
)


@pytest.mark.unit
def test_estimate_cost_known_model():
    # gemini-3-flash-preview: 0.5e-6 in, 3e-6 out
    cost = estimate_cost("google/gemini-3-flash-preview", 1_000_000, 1_000_000)
    assert cost == pytest.approx(0.5 + 3.0)


@pytest.mark.unit
def test_estimate_cost_unknown_uses_max_rate():
    # unknown model -> most expensive known rate (conservative)
    cost = estimate_cost("nonexistent/model", 1_000_000, 0)
    assert cost > 0


@pytest.mark.unit
def test_cost_record_is_immutable():
    rec = CostRecord("m", 10, 5, 0.01)
    with pytest.raises(dataclasses.FrozenInstanceError):
        rec.cost_usd = 99.0  # type: ignore[misc]


@pytest.mark.unit
def test_budget_guard_reserve_blocks_over_ceiling():
    guard = BudgetGuard(hard_stop_usd=0.10, warn_usd=0.05)
    guard.record(CostRecord("m", 0, 0, 0.09))
    # 0.09 + 0.02 = 0.11 >= 0.10 -> must raise BEFORE the call
    with pytest.raises(BudgetExceededError):
        guard.reserve(0.02)


@pytest.mark.unit
def test_budget_guard_allows_under_ceiling():
    guard = BudgetGuard(hard_stop_usd=1.0)
    guard.reserve(0.5)  # should not raise
    guard.record(CostRecord("m", 100, 50, 0.5))
    assert guard.total == pytest.approx(0.5)
    assert guard.n_calls == 1


@pytest.mark.unit
def test_budget_guard_summary_by_model():
    guard = BudgetGuard()
    guard.record(CostRecord("a", 10, 1, 0.01))
    guard.record(CostRecord("a", 20, 2, 0.02))
    guard.record(CostRecord("b", 5, 1, 0.03))
    summ = guard.summary_by_model()
    assert summ["a"]["calls"] == 2
    assert summ["a"]["cost"] == pytest.approx(0.03)
    assert summ["b"]["calls"] == 1
