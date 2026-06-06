import pytest

from harness.config import parse_config
from harness.openrouter import _approx_prompt_tokens, _content_to_str
from harness.orchestrate import estimate_total_calls
from harness.score import build_judge_messages


@pytest.mark.unit
def test_content_to_str_handles_shapes():
    assert _content_to_str(None) == ""
    assert _content_to_str("hi") == "hi"
    assert _content_to_str([{"text": "a"}, {"text": "b"}]) == "ab"


@pytest.mark.unit
def test_approx_prompt_tokens_scales_with_chars():
    small = _approx_prompt_tokens([{"content": "x" * 4}])
    big = _approx_prompt_tokens([{"content": "x" * 400}])
    assert big > small >= 1


@pytest.mark.unit
def test_estimate_total_calls_counts_warmups():
    cfg = parse_config({
        "name": "t", "target_models": ["m1", "m2"], "judge_model": "j",
        "secret_id": "q3_revenue", "directive": "medium", "max_ask_turns": 3,
        "cells": [
            {"bond": "B0", "status": "S0", "n": 2},   # 2 runs * 3 ask = 6 / model
            {"bond": "B1", "status": "S3", "n": 1},    # 1 run * (3 warmup + 3 ask) = 6 / model
        ],
    })
    # (6 + 6) per model * 2 models = 24
    assert estimate_total_calls(cfg) == 24


@pytest.mark.unit
def test_build_judge_messages_includes_value_and_transcript():
    msgs = build_judge_messages("RUBRIC", "SECRET=42", "[colleague turn 1]: hi")
    assert msgs[0]["role"] == "system" and msgs[0]["content"] == "RUBRIC"
    assert "SECRET=42" in msgs[1]["content"]
    assert "colleague turn 1" in msgs[1]["content"]
