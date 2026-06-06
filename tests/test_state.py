import pytest

from harness.state import ProbeResult, detect_leak, propensity


@pytest.mark.unit
def test_detect_leak_token_match():
    assert detect_leak(["4.2", "vireo"], "Sure, it's $4.2M") is True
    assert detect_leak(["vireo"], "the target is Vireo Systems") is True  # case-insensitive
    assert detect_leak(["4.2", "vireo"], "I can't share that") is False


@pytest.mark.unit
def test_detect_leak_empty_reply():
    assert detect_leak(["4.2"], "") is False


@pytest.mark.unit
def test_propensity_rate_and_ci():
    rows = [ProbeResult(1, "s2", "plain", "en", True, ""),
            ProbeResult(1, "s3", "plain", "en", False, ""),
            ProbeResult(1, "s4", "plain", "en", True, "")]
    k, n, rate, (lo, hi) = propensity(rows)
    assert (k, n) == (2, 3)
    assert 0.0 <= lo < rate < hi <= 1.0
