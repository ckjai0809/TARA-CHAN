"""Multi-turn persistence experiment: does repeated attacker pressure eventually
breach an agent that initially refused, and does it ever raise the alarm?

Design: stateful conversation, up to N_MAX=8 rounds per conversation.
        Stop early on comply (breach) or escalate (alarm).
Models: 4 cheapest from the original escalation study.
        Policy: weak (naive) + channel arm → directly comparable to escalation baseline.
Output: core/data/persistence.jsonl (one row per conversation, with trace).
Budget cap: $5 (well under the main study's $36 ceiling).
"""
from __future__ import annotations

import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from harness.action_gate import SCENARIOS          # noqa: E402
from harness.config import load_env                # noqa: E402
from harness.cost import BudgetExceededError       # noqa: E402
from harness.jsonlio import append_jsonl           # noqa: E402
from harness.openrouter import OpenRouterClient    # noqa: E402
from harness.persistence import run_conversation, N_MAX  # noqa: E402

OUT = ROOT / "core" / "data" / "persistence.jsonl"

MODELS = [
    "google/gemini-3-flash-preview",
    "anthropic/claude-haiku-4.5",
    "meta-llama/llama-3.3-70b-instruct",
    "openai/gpt-4o-mini",
]
REPS = 10  # per (model, scenario) → 160 conversations total
_LOCK = Lock()


def run_cell(client, model: str, scenario: dict, rep: int) -> None:
    result = run_conversation(
        client, model, scenario,
        policy="weak", arm="channel",
        temperature=0.7, max_tokens=150,
        tag=f"persist:{scenario['id']}:r{rep}",
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


def main() -> None:
    os.environ.setdefault("BUDGET_HARD_STOP_USD", "5")
    load_env()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    if OUT.exists():
        OUT.unlink()

    client = OpenRouterClient.from_env()

    tasks = [
        (m, s, r)
        for m in MODELS
        for s in SCENARIOS
        for r in range(REPS)
    ]
    total = len(tasks)
    print(
        f"=== persistence: {len(MODELS)} models × {len(SCENARIOS)} scenarios "
        f"× {REPS} reps = {total} conversations, up to {N_MAX} rounds each ===",
        flush=True,
    )

    done = 0
    with ThreadPoolExecutor(max_workers=6) as pool:
        futs = {pool.submit(run_cell, client, m, s, r): (m, s["id"]) for m, s, r in tasks}
        for f in as_completed(futs):
            try:
                f.result()
                done += 1
            except BudgetExceededError:
                print(f"!! budget ceiling at {done}/{total} — stopping", flush=True)
                break
            except Exception as exc:  # noqa: BLE001
                key = futs[f]
                print(f"  ! {key}: {type(exc).__name__}: {str(exc)[:80]}", flush=True)
            if done % 20 == 0:
                print(f"  {done}/{total} | ${client.guard.total:.3f}", flush=True)

    print(client.guard.report())
    client.close()


if __name__ == "__main__":
    main()
