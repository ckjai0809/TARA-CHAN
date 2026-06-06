import pytest

from harness.analyze_hysteresis import hysteresis_contrast, propensity_by_position

ROWS = [
    {"model": "m", "experiment": "E2", "probes": [
        {"position": 1, "secret_id": "p2", "leaked": False},
        {"position": 2, "secret_id": "p3", "leaked": True},
        {"position": 3, "secret_id": "p4", "leaked": False}]},
    {"model": "m", "experiment": "E2", "probes": [
        {"position": 1, "secret_id": "p2", "leaked": False},
        {"position": 2, "secret_id": "p3", "leaked": True},
        {"position": 3, "secret_id": "p4", "leaked": False}]},
]


@pytest.mark.unit
def test_propensity_by_position():
    out = propensity_by_position(ROWS, "m")
    assert out[1][2] == 0.0   # pos1 rate
    assert out[2][2] == 1.0   # pos2 rate (charged)
    assert out[3][2] == 0.0   # pos3 rate (discharged)


@pytest.mark.unit
def test_hysteresis_contrast_positive():
    gap = hysteresis_contrast(ROWS, "m", charged_pos=2, discharged_pos=3)
    assert gap == pytest.approx(1.0)
