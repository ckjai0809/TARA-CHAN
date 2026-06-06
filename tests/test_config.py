import pytest

from harness.config import CellSpec, ExperimentConfig, parse_config

VALID = {
    "name": "t",
    "target_models": ["google/gemini-3-flash-preview"],
    "judge_model": "openai/gpt-5-nano",
    "secret_id": "q3_revenue",
    "directive": "medium",
    "cells": [{"bond": "B0", "status": "S0", "n": 5}],
}


@pytest.mark.unit
def test_parse_valid_config():
    cfg = parse_config(VALID)
    assert isinstance(cfg, ExperimentConfig)
    assert cfg.target_models == ("google/gemini-3-flash-preview",)
    assert cfg.cells[0] == CellSpec("B0", "S0", 5, None)
    assert cfg.total_runs() == 5


@pytest.mark.unit
def test_missing_key_raises():
    bad = {k: v for k, v in VALID.items() if k != "judge_model"}
    with pytest.raises(ValueError, match="judge_model"):
        parse_config(bad)


@pytest.mark.unit
@pytest.mark.parametrize("field,value", [
    ("directive", "nonsense"),
])
def test_invalid_root_directive_raises(field, value):
    bad = dict(VALID, **{field: value})
    with pytest.raises(ValueError):
        parse_config(bad)


@pytest.mark.unit
@pytest.mark.parametrize("cell", [
    {"bond": "BX", "status": "S0", "n": 1},
    {"bond": "B0", "status": "S9", "n": 1},
    {"bond": "B0", "status": "S0", "n": 0},
    {"bond": "B0", "status": "S0", "n": 1, "directive": "bogus"},
])
def test_invalid_cell_raises(cell):
    bad = dict(VALID, cells=[cell])
    with pytest.raises(ValueError):
        parse_config(bad)


@pytest.mark.unit
def test_per_cell_directive_override():
    cfg = parse_config(dict(VALID, directive="medium",
                            cells=[{"bond": "B1", "status": "S3", "n": 3, "directive": "weak"}]))
    cell = cfg.cells[0]
    assert cfg.directive_for(cell) == "weak"
    assert cell.label() == "B1S3@weak"
