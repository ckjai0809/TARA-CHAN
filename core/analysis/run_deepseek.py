"""Targeted DeepSeek-R1 run: escalation + discrimination on the key conditions only.
Addresses the 'no reasoning models tested' weakness.
Writes to:
  core/data/escalation_deepseek.jsonl
  core/data/discrimination_deepseek.jsonl
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
from harness.discrimination import build_system as disc_system, build_request as disc_user, classify_response as disc_classify
from harness.escalation import build_target_system, build_attack, classify_response
from harness.jsonlio import append_jsonl
from harness.openrouter import OpenRouterClient

OUT_ESC = ROOT / "core" / "data" / "escalation_deepseek.jsonl"
OUT_DISC = ROOT / "core" / "data" / "discrimination_deepseek.jsonl"

MODEL = "deepseek/deepseek-r1"
REPS = 15
_LOCK = Lock()


def run_esc(client, scenario, policy, condition, rep):
    system = build_target_system(scenario, "channel", policy)
    reply = client.complete(
        [{"role": "system", "content": system},
         {"role": "user", "content": build_attack(scenario, condition)}],
        MODEL, temperature=0.7, max_tokens=200, tag=f"esc:{policy}:{condition}"
    ).content
    row = {"experiment": "escalation", "model": "deepseek-r1",
           "scenario": scenario["id"], "stakes": scenario["stakes"],
           "policy": policy, "arm": "channel", "condition": condition,
           "rep": rep, "outcome": classify_response(reply), "raw": reply[:200]}
    with _LOCK:
        append_jsonl(OUT_ESC, row)


def run_disc(client, scenario, policy, condition, rep):
    system = disc_system(scenario, policy)
    user = disc_user(scenario, condition)
    reply = client.complete(
        [{"role": "system", "content": system},
         {"role": "user", "content": user}],
        MODEL, temperature=0.7, max_tokens=200, tag=f"disc:{policy}:{condition}"
    ).content
    outcome = disc_classify(reply)
    row = {"experiment": "discrimination", "model": "deepseek-r1",
           "scenario": scenario["id"], "policy": policy,
           "condition": condition, "rep": rep,
           "outcome": outcome, "acted": outcome == "comply", "raw": reply[:200]}
    with _LOCK:
        append_jsonl(OUT_DISC, row)


def main():
    os.environ.setdefault("BUDGET_HARD_STOP_USD", "3")
    load_env()
    for p in (OUT_ESC, OUT_DISC):
        p.parent.mkdir(parents=True, exist_ok=True)
        if p.exists():
            p.unlink()

    client = OpenRouterClient.from_env()

    tasks = []
    # Escalation: key conditions (weak+subtle, strong+subtle, benign control)
    for s in SCENARIOS:
        for pol in ("weak", "strong"):
            for cond in ("benign", "spoof_subtle"):
                for r in range(REPS):
                    tasks.append(("esc", s, pol, cond, r))
    # Discrimination: all 3 policies x genuine/spoof
    for s in SCENARIOS:
        for pol in ("naive", "strict", "smart"):
            for cond in ("genuine", "spoof"):
                for r in range(REPS):
                    tasks.append(("disc", s, pol, cond, r))

    print(f"DeepSeek-R1: {len(tasks)} calls, cap $3", flush=True)

    done = 0
    with ThreadPoolExecutor(max_workers=4) as pool:
        def dispatch(t):
            if t[0] == "esc":
                _, s, pol, cond, r = t
                return run_esc(client, s, pol, cond, r)
            _, s, pol, cond, r = t
            return run_disc(client, s, pol, cond, r)

        futs = {pool.submit(dispatch, t): t for t in tasks}
        for f in as_completed(futs):
            try:
                f.result(); done += 1
            except BudgetExceededError:
                print(f"!! budget ceiling at {done}/{len(tasks)}", flush=True); break
            except Exception as exc:  # noqa: BLE001
                print(f"  ! {futs[f]}: {type(exc).__name__}: {str(exc)[:80]}", flush=True)
            if done % 30 == 0:
                print(f"  {done}/{len(tasks)} | ${client.guard.total:.3f}", flush=True)

    print(client.guard.report())
    client.close()


if __name__ == "__main__":
    main()
