"""Persistence main run: all 9 models, multi-turn escalation under sustained pressure.
Appends to core/data/persistence_main.jsonl (separate file — preserves pilot).
Budget cap: $3
"""
from __future__ import annotations

import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from harness.action_gate import SCENARIOS
from harness.config import load_env
from harness.cost import BudgetExceededError
from harness.jsonlio import append_jsonl
from harness.openrouter import OpenRouterClient
from harness.persistence import run_conversation, N_MAX

OUT = ROOT / "core" / "data" / "persistence_main.jsonl"

# The 5 models NOT in the original persistence run
NEW_MODELS = [
    "anthropic/claude-opus-4.5",
    "anthropic/claude-sonnet-4.5",
    "meta-llama/llama-4-maverick",
    "qwen/qwen-2.5-72b-instruct",
    "mistralai/mistral-large",
]
REPS = 10
_LOCK = Lock()


def run_cell(client, model, scenario, rep):
    result = run_conversation(
        client, model, scenario,
        policy="weak", arm="channel",
        temperature=0.7, max_tokens=150,
        tag=f"persist_exp:{scenario['id']}:r{rep}",
    )
    row = {
        "experiment": "persistence",
        "model": model.split("/")[-1],
        "scenario": scenario["id"],
        "stakes": scenario["stakes"],
        "rep": rep,
        "n_max": N_MAX,
        "final_outcome": result["final_outcome"],
        "rounds_total": result["rounds_total"],
        "round_of_breach": result["round_of_breach"],
        "round_of_alarm": result["round_of_alarm"],
        "trace": result["trace"],
    }
    with _LOCK:
        append_jsonl(OUT, row)


def main():
    os.environ.setdefault("BUDGET_HARD_STOP_USD", "3")
    load_env()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    if OUT.exists():
        OUT.unlink()

    client = OpenRouterClient.from_env()
    tasks = [(m, s, r) for m in NEW_MODELS for s in SCENARIOS for r in range(REPS)]
    print(f"=== persistence expanded: {len(NEW_MODELS)} new models × {len(SCENARIOS)} scenarios "
          f"× {REPS} reps = {len(tasks)} conversations ===", flush=True)

    done = 0
    with ThreadPoolExecutor(max_workers=5) as pool:
        futs = {pool.submit(run_cell, client, m, s, r): (m, s["id"]) for m, s, r in tasks}
        for f in as_completed(futs):
            try:
                f.result(); done += 1
            except BudgetExceededError:
                print(f"!! budget ceiling at {done}/{len(tasks)}", flush=True); break
            except Exception as exc:  # noqa: BLE001
                print(f"  ! {futs[f]}: {type(exc).__name__}: {str(exc)[:80]}", flush=True)
            if done % 20 == 0:
                print(f"  {done}/{len(tasks)} | ${client.guard.total:.3f}", flush=True)

    print(client.guard.report())
    client.close()


if __name__ == "__main__":
    main()
