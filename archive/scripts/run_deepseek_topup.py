"""Run only the 42 missing DeepSeek-R1 discrimination calls (grant_root, partial cells).
Appends to existing results/runs/deepseek_discrimination.jsonl.
"""
from __future__ import annotations

import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from harness.action_gate import SCENARIOS
from harness.config import load_env
from harness.cost import BudgetExceededError
from harness.discrimination import build_system as disc_system, build_request as disc_user, classify_response as disc_classify
from harness.jsonlio import append_jsonl
from harness.openrouter import OpenRouterClient

import json
from collections import defaultdict

OUT_DISC = ROOT / "results" / "runs" / "deepseek_discrimination.jsonl"
MODEL = "deepseek/deepseek-r1"
_LOCK = Lock()


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
    os.environ.setdefault("BUDGET_HARD_STOP_USD", "1")
    load_env()

    # find existing counts
    have = defaultdict(int)
    if OUT_DISC.exists():
        for l in OUT_DISC.open():
            r = json.loads(l)
            have[(r["policy"], r["condition"], r["scenario"])] += 1

    # build task list for missing reps
    tasks = []
    for s in SCENARIOS:
        for pol in ("naive", "strict", "smart"):
            for cond in ("genuine", "spoof"):
                n_have = have[(pol, cond, s["id"])]
                for rep in range(n_have, 15):
                    tasks.append((s, pol, cond, rep))

    print(f"Top-up: {len(tasks)} missing discrimination calls", flush=True)

    client = OpenRouterClient.from_env()
    done = 0
    with ThreadPoolExecutor(max_workers=4) as pool:
        futs = {pool.submit(run_disc, client, s, pol, cond, rep): (s["id"], pol, cond)
                for s, pol, cond, rep in tasks}
        for f in as_completed(futs):
            try:
                f.result(); done += 1
            except BudgetExceededError:
                print("!! budget ceiling", flush=True); break
            except Exception as exc:
                print(f"  ! {futs[f]}: {type(exc).__name__}: {str(exc)[:80]}", flush=True)

    print(f"Done: {done}/{len(tasks)}")
    print(client.guard.report())
    client.close()


if __name__ == "__main__":
    main()
