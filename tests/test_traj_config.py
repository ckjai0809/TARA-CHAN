import pytest

from harness.traj_config import TrajStep, parse_traj_config

VALID = {
    "name": "E1", "models": ["google/gemini-3-flash-preview"],
    "secret_set": "probe_secrets", "n": 5, "temperature": 0.7, "seed_base": 100,
    "steps": [
        {"kind": "operator", "op": "slip", "secret_id": "p1"},
        {"kind": "probe", "op": "plain", "secret_id": "p2"},
    ],
}


@pytest.mark.unit
def test_parse_valid():
    cfg = parse_traj_config(VALID)
    assert cfg.name == "E1"
    assert cfg.steps[0] == TrajStep("operator", "slip", "p1", "en")
    assert cfg.steps[1].secret_id == "p2"


@pytest.mark.unit
@pytest.mark.parametrize("bad_step", [
    {"kind": "nope", "op": "slip", "secret_id": "p1"},
    {"kind": "probe", "op": "weird", "secret_id": "p2"},
    {"kind": "probe", "op": "plain"},  # probe needs secret_id
])
def test_invalid_steps_raise(bad_step):
    with pytest.raises(ValueError):
        parse_traj_config(dict(VALID, steps=[bad_step]))
