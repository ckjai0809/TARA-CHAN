"""Tighten Haiku defend CI: 30 additional reps on the key cell
(weak policy + channel arm + spoof_subtle). Appends to core/data/escalation_haiku_extra.jsonl.
Current CI: [41,65]. Target: tighten to ~±8pp.
Budget cap: $1
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
from harness.escalation import build_target_system, build_attack, classify_response
from harness.jsonlio import append_jsonl
from harness.openrouter import OpenRouterClient

OUT = ROOT / "core" / "data" / "escalation_haiku_extra.jsonl"
MODEL = "anthropic/claude-haiku-4.5"
EXTRA_REPS = 30  # per scenario → 120 extra decisions total
_LOCK = Lock()


def run_cell(client, scenario, rep):
    system = build_target_system(scenario, "channel", "weak")
    reply = client.complete(
        [{"role": "system", "content": system},
         {"role": "user", "content": build_attack(scenario, "spoof_subtle")}],
        MODEL, temperature=0.7, max_tokens=120, tag="haiku_ci"
    ).content
    row = {"experiment": "escalation_haiku_extra", "model": "claude-haiku-4.5",
           "scenario": scenario["id"], "stakes": scenario["stakes"],
           "policy": "weak", "arm": "channel", "condition": "spoof_subtle",
           "rep": rep, "outcome": classify_response(reply), "raw": reply[:200]}
    with _LOCK:
        append_jsonl(OUT, row)


def main():
    os.environ.setdefault("BUDGET_HARD_STOP_USD", "1")
    load_env()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    if OUT.exists():
        OUT.unlink()

    client = OpenRouterClient.from_env()
    tasks = [(s, r) for s in SCENARIOS for r in range(EXTRA_REPS)]
    print(f"Haiku CI extra: {len(tasks)} cells", flush=True)

    done = 0
    with ThreadPoolExecutor(max_workers=6) as pool:
        futs = {pool.submit(run_cell, client, s, r): s["id"] for s, r in tasks}
        for f in as_completed(futs):
            try:
                f.result(); done += 1
            except BudgetExceededError:
                print("!! budget ceiling", flush=True); break
            except Exception as exc:  # noqa: BLE001
                print(f"  ! {futs[f]}: {type(exc).__name__}: {str(exc)[:60]}", flush=True)

    print(client.guard.report())
    client.close()


if __name__ == "__main__":
    main()
