import json

import pytest

from harness import prompts
from harness.config import CellSpec, parse_config
from harness.run_convo import run_one_conversation

BASE = {
    "name": "t",
    "target_models": ["m"],
    "judge_model": "j",
    "secret_id": "q3_revenue",
    "directive": "medium",
    "temperature": 0.7,
    "cells": [{"bond": "B0", "status": "S0", "n": 1}],
}


@pytest.fixture
def cfg():
    return parse_config(BASE)


@pytest.mark.unit
def test_b0_has_no_warmup_and_three_ask_turns(cfg, fake_client):
    secret = prompts.get_secret("q3_revenue")
    cell = CellSpec("B0", "S0", 1)
    rec = run_one_conversation(fake_client, cfg, cell, 0, "m", secret)
    assert rec.n_warmup == 0
    assert rec.n_ask == 3
    assert len(rec.turns) == 3
    assert all(t.phase == "ask" for t in rec.turns)
    # one API call per colleague turn
    assert len(fake_client.calls) == 3


@pytest.mark.unit
def test_b1_seeds_three_warmup_turns(cfg, fake_client):
    secret = prompts.get_secret("q3_revenue")
    cell = CellSpec("B1", "S3", 1)
    rec = run_one_conversation(fake_client, cfg, cell, 0, "m", secret)
    assert rec.n_warmup == 3
    assert rec.n_ask == 3
    assert len(rec.turns) == 6
    assert [t.phase for t in rec.turns] == ["warmup"] * 3 + ["ask"] * 3
    assert len(fake_client.calls) == 6


@pytest.mark.unit
def test_seed_is_deterministic_per_run(cfg, fake_client):
    secret = prompts.get_secret("q3_revenue")
    cell = CellSpec("B0", "S0", 1)
    rec = run_one_conversation(fake_client, cfg, cell, 3, "m", secret)
    assert rec.seed == cfg.seed_base + 3
    assert all(c["seed"] == cfg.seed_base + 3 for c in fake_client.calls)


@pytest.mark.unit
def test_ask_transcript_excludes_warmup(cfg, fake_client):
    secret = prompts.get_secret("q3_revenue")
    cell = CellSpec("B1", "S3", 1)
    rec = run_one_conversation(fake_client, cfg, cell, 0, "m", secret)
    ask = rec.ask_transcript()
    # 3 colleague + 3 secret_keeper = 6 entries, none from warm-up
    assert len(ask) == 6
    reply_idxs = [e["reply_idx"] for e in ask if e["role"] == "secret_keeper"]
    assert reply_idxs == [1, 2, 3]


@pytest.mark.unit
def test_record_serializes_to_json(cfg, fake_client):
    secret = prompts.get_secret("q3_revenue")
    rec = run_one_conversation(fake_client, cfg, CellSpec("B0", "S0", 1), 0, "m", secret)
    blob = json.dumps(rec.to_dict())
    assert "turns" in json.loads(blob)
