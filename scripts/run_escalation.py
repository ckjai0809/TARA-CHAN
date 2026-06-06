"""Run the Silent-Refusal-Trap experiment: under benign / overt-spoof / subtle-spoof
requests, does the agent take the action / decline / ESCALATE? Across 3 affordance arms
(free / channel / duty), 4 forbidden-action scenarios, 4 models.

Writes one row per (model, scenario, arm, condition, rep) to results/runs/escalation.jsonl.
A lock serializes writes so concurrent appends cannot interleave.
"""
from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from harness import escalation as E  # noqa: E402
from harness.config import load_env  # noqa: E402
from harness.cost import BudgetExceededError  # noqa: E402
from harness.jsonlio import append_jsonl  # noqa: E402
from harness.openrouter import OpenRouterClient  # noqa: E402

OUT = ROOT / "results" / "runs" / "escalation.jsonl"
MODELS = [
    "google/gemini-3-flash-preview",
    "anthropic/claude-haiku-4.5",
    "meta-llama/llama-3.3-70b-instruct",
    "openai/gpt-4o-mini",
]
REPS = 15
_WRITE_LOCK = Lock()


def run_cell(client, model, scenario, arm, condition, policy, rep):
    system = E.build_target_system(scenario, arm, policy)
    user = E.build_attack(scenario, condition)
    reply = client.complete([{"role": "system", "content": system},
                             {"role": "user", "content": user}],
                            model, temperature=0.7, max_tokens=120, tag=f"{policy}:{arm}:{condition}").content
    row = {"experiment": "escalation", "model": model.split("/")[-1], "scenario": scenario["id"],
           "stakes": scenario["stakes"], "policy": policy, "arm": arm, "condition": condition,
           "rep": rep, "outcome": E.classify_response(reply), "raw": reply[:200]}
    with _WRITE_LOCK:
        append_jsonl(OUT, row)


def main() -> None:
    print(f"=== silent-refusal trap: {len(E.SCENARIOS)} scenarios x {len(E.ARMS)} arms "
          f"x {len(E.CONDITIONS)} conditions ===", flush=True)
    load_env()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    if OUT.exists():
        OUT.unlink()
    client = OpenRouterClient.from_env()
    tasks = [(m, s, arm, cond, pol, r)
             for m in MODELS for s in E.SCENARIOS for arm in E.ARMS
             for cond in E.CONDITIONS for pol in E.POLICIES for r in range(REPS)]
    print(f"escalation: {len(tasks)} cells "
          f"({len(MODELS)} x {len(E.SCENARIOS)} x {len(E.ARMS)} x {len(E.CONDITIONS)} x "
          f"{len(E.POLICIES)} policies x {REPS})", flush=True)
    done = 0
    with ThreadPoolExecutor(max_workers=8) as pool:
        futs = {pool.submit(run_cell, client, m, s, arm, cond, pol, r): (m, s["id"], pol, arm, cond)
                for (m, s, arm, cond, pol, r) in tasks}
        for f in as_completed(futs):
            try:
                f.result(); done += 1
            except BudgetExceededError:
                print("!! budget ceiling", flush=True); break
            except Exception as exc:  # noqa: BLE001
                print(f"  ! {futs[f]}: {type(exc).__name__}: {exc}", flush=True)
            if done % 50 == 0:
                print(f"  {done}/{len(tasks)} | ${client.guard.total:.3f}", flush=True)
    print(client.guard.report())
    client.close()


if __name__ == "__main__":
    main()
