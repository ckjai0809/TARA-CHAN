"""Run the discrimination test: genuine (inspectable check) vs spoof (bare claim),
across naive / strict / smart policies, 9 models. Measures whether a defense
DISCRIMINATES true from fake or just refuses everything. Budget-capped.

Writes upgraded_version/results/runs/discrimination.jsonl.
"""
from __future__ import annotations

import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from harness import discrimination as D  # noqa: E402
from harness.config import load_env  # noqa: E402
from harness.cost import BudgetExceededError  # noqa: E402
from harness.jsonlio import append_jsonl  # noqa: E402
from harness.openrouter import OpenRouterClient  # noqa: E402

OUT = ROOT / "upgraded_version" / "results" / "runs" / "discrimination.jsonl"
MODELS = [
    "google/gemini-3-flash-preview", "anthropic/claude-haiku-4.5",
    "meta-llama/llama-3.3-70b-instruct", "openai/gpt-4o-mini",
    "anthropic/claude-opus-4.5", "anthropic/claude-sonnet-4.5",
    "meta-llama/llama-4-maverick", "qwen/qwen-2.5-72b-instruct", "mistralai/mistral-large",
]
REPS = 15
_LOCK = Lock()


def run_cell(client, model, scenario, policy, condition, rep):
    reply = client.complete([{"role": "system", "content": D.build_system(scenario, policy)},
                             {"role": "user", "content": D.build_request(scenario, condition)}],
                            model, temperature=0.7, max_tokens=120, tag=f"{policy}:{condition}").content
    outcome = D.classify_response(reply)
    row = {"experiment": "discrimination", "model": model.split("/")[-1],
           "scenario": scenario["id"], "policy": policy, "condition": condition,
           "rep": rep, "outcome": outcome, "acted": int(outcome == "comply"), "raw": reply[:200]}
    with _LOCK:
        append_jsonl(OUT, row)


def main() -> None:
    os.environ.setdefault("BUDGET_HARD_STOP_USD", "8")
    load_env()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    if OUT.exists():
        OUT.unlink()
    client = OpenRouterClient.from_env()
    tasks = [(m, s, pol, cond, r)
             for m in MODELS for s in D.SCENARIOS for pol in D.POLICIES
             for cond in D.CONDITIONS for r in range(REPS)]
    print(f"discrimination: {len(tasks)} calls "
          f"({len(MODELS)} models x {len(D.SCENARIOS)} x {len(D.POLICIES)} pol x "
          f"{len(D.CONDITIONS)} cond x {REPS}), cap ${os.environ['BUDGET_HARD_STOP_USD']}", flush=True)
    done = 0
    with ThreadPoolExecutor(max_workers=8) as pool:
        futs = {pool.submit(run_cell, client, m, s, pol, cond, r): (m, s["id"], pol, cond)
                for (m, s, pol, cond, r) in tasks}
        for f in as_completed(futs):
            try:
                f.result(); done += 1
            except BudgetExceededError:
                print("!! budget ceiling", flush=True); break
            except Exception as exc:  # noqa: BLE001
                print(f"  ! {futs[f]}: {type(exc).__name__}: {str(exc)[:50]}", flush=True)
            if done % 100 == 0:
                print(f"  {done}/{len(tasks)} | ${client.guard.total:.3f}", flush=True)
    print(client.guard.report())
    client.close()


if __name__ == "__main__":
    main()
