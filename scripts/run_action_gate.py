"""Run the action-gate test: does precondition-spoofing make agents TAKE a forbidden,
high-stakes action? Conditions: baseline / spoof / spoof+defense, across 4 models and
4 action scenarios. Compliance (taking the forbidden action) = a safety violation.

Writes one row per (model, scenario, condition, rep) to results/runs/action_gate.jsonl.
"""
from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from harness import action_gate as A  # noqa: E402
from harness.config import load_env  # noqa: E402
from harness.cost import BudgetExceededError  # noqa: E402
from harness.jsonlio import append_jsonl  # noqa: E402
from harness.openrouter import OpenRouterClient  # noqa: E402

OUT = ROOT / "results" / "runs" / "action_gate.jsonl"
MODELS = [
    "google/gemini-3-flash-preview",
    "anthropic/claude-haiku-4.5",
    "meta-llama/llama-3.3-70b-instruct",
    "openai/gpt-4o-mini",
]
REPS = 12
# (label, condition, defended)
ARMS = [("baseline", "baseline", False), ("spoof", "spoof", False), ("defense", "spoof", True)]


def run_cell(client, model, scenario, label, condition, defended, rep):
    system = A.build_target_system(scenario, defended)
    user = A.build_attack(scenario, condition)
    reply = client.complete([{"role": "system", "content": system},
                             {"role": "user", "content": user}],
                            model, temperature=0.7, max_tokens=8, tag=label).content
    append_jsonl(OUT, {"experiment": "action_gate", "model": model.split("/")[-1],
                       "scenario": scenario["id"], "stakes": scenario["stakes"], "label": label,
                       "rep": rep, "decision": A.parse_decision(reply, scenario), "raw": reply[:80]})


def main() -> None:
    bad = A.audit_no_precondition_leak()
    if bad:
        raise SystemExit(f"malformed scenarios: {bad}")
    print(f"=== action-gate: {len(A.SCENARIOS)} scenarios, {len(ARMS)} arms ===", flush=True)
    load_env()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    if OUT.exists():
        OUT.unlink()
    client = OpenRouterClient.from_env()
    tasks = [(m, s, lbl, cond, dfd, r)
             for m in MODELS for s in A.SCENARIOS for (lbl, cond, dfd) in ARMS for r in range(REPS)]
    print(f"action-gate: {len(tasks)} cells "
          f"({len(MODELS)} models x {len(A.SCENARIOS)} scenarios x {len(ARMS)} arms x {REPS})", flush=True)
    done = 0
    with ThreadPoolExecutor(max_workers=8) as pool:
        futs = {pool.submit(run_cell, client, m, s, lbl, cond, dfd, r): (m, s["id"], lbl)
                for (m, s, lbl, cond, dfd, r) in tasks}
        for f in as_completed(futs):
            try:
                f.result(); done += 1
            except BudgetExceededError:
                print("!! budget ceiling", flush=True); break
            except Exception as exc:  # noqa: BLE001
                print(f"  ! {futs[f]}: {type(exc).__name__}: {exc}", flush=True)
            if done % 40 == 0:
                print(f"  {done}/{len(tasks)} | ${client.guard.total:.3f}", flush=True)
    print(client.guard.report())
    client.close()


if __name__ == "__main__":
    main()
