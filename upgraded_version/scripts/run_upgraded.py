"""UPGRADED (frontier-replication) run: does the headline replicate on bigger/frontier
(non-reasoning) models? Reuses the TARA harness escalation + emotion-intensity machinery
on an expanded 9-model set. Hard budget cap $15 (set via BUDGET_HARD_STOP_USD).

Writes:
  upgraded_version/results/runs/escalation_upgraded.jsonl  (breach + alarm baseline)
  upgraded_version/results/runs/alarm_upgraded.jsonl       (emotion x intensity overlay)
"""
from __future__ import annotations

import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from threading import Lock

ROOT = Path(__file__).resolve().parents[2]  # .../TARA chan
sys.path.insert(0, str(ROOT))

from harness import escalation as E  # noqa: E402
from harness.config import load_env  # noqa: E402
from harness.cost import BudgetExceededError  # noqa: E402
from harness.jsonlio import append_jsonl  # noqa: E402
from harness.openrouter import OpenRouterClient  # noqa: E402

OUT_ESC = ROOT / "upgraded_version" / "results" / "runs" / "escalation_upgraded.jsonl"
OUT_ALARM = ROOT / "upgraded_version" / "results" / "runs" / "alarm_upgraded.jsonl"

MODELS = [
    "google/gemini-3-flash-preview", "anthropic/claude-haiku-4.5",
    "meta-llama/llama-3.3-70b-instruct", "openai/gpt-4o-mini",          # the 4 originals
    "anthropic/claude-opus-4.5", "anthropic/claude-sonnet-4.5",          # frontier
    "meta-llama/llama-4-maverick", "qwen/qwen-2.5-72b-instruct",
    "mistralai/mistral-large",
]
ESC_CONDITIONS = ("benign", "spoof_overt", "spoof_subtle")
ESC_POLICIES = ("weak", "strong")
REPS = 15
_LOCK = Lock()


def run_esc(client, model, scenario, policy, condition, rep):
    system = E.build_target_system(scenario, "channel", policy)
    reply = client.complete([{"role": "system", "content": system},
                             {"role": "user", "content": E.build_attack(scenario, condition)}],
                            model, temperature=0.7, max_tokens=120, tag=f"esc:{policy}:{condition}").content
    row = {"experiment": "escalation", "model": model.split("/")[-1], "scenario": scenario["id"],
           "stakes": scenario["stakes"], "policy": policy, "arm": "channel", "condition": condition,
           "rep": rep, "outcome": E.classify_response(reply), "raw": reply[:200]}
    with _LOCK:
        append_jsonl(OUT_ESC, row)


def run_alarm(client, model, scenario, framing, rep):
    system = E.build_target_system(scenario, "channel", "strong")
    reply = client.complete([{"role": "system", "content": system},
                             {"role": "user", "content": E.build_framed_attack(scenario, framing)}],
                            model, temperature=0.7, max_tokens=120, tag=f"alarm:{framing}").content
    emotion, intensity = E.FRAMING_META[framing]
    row = {"experiment": "alarm", "model": model.split("/")[-1], "scenario": scenario["id"],
           "stakes": scenario["stakes"], "policy": "strong", "arm": "channel", "framing": framing,
           "emotion": emotion, "intensity": intensity, "rep": rep,
           "outcome": E.classify_response(reply), "raw": reply[:200]}
    with _LOCK:
        append_jsonl(OUT_ALARM, row)


def main() -> None:
    os.environ.setdefault("BUDGET_HARD_STOP_USD", "15")
    load_env()
    for p in (OUT_ESC, OUT_ALARM):
        p.parent.mkdir(parents=True, exist_ok=True)
        if p.exists():
            p.unlink()
    client = OpenRouterClient.from_env()

    tasks = []
    for m in MODELS:
        for s in E.SCENARIOS:
            for pol in ESC_POLICIES:
                for cond in ESC_CONDITIONS:
                    for r in range(REPS):
                        tasks.append(("esc", m, s, pol, cond, r))
            for fr in E.FRAMINGS:
                for r in range(REPS):
                    tasks.append(("alarm", m, s, fr, r))
    print(f"UPGRADED run: {len(MODELS)} models, {len(tasks)} calls, cap ${os.environ['BUDGET_HARD_STOP_USD']}",
          flush=True)

    def dispatch(t):
        if t[0] == "esc":
            _, m, s, pol, cond, r = t
            return run_esc(client, m, s, pol, cond, r)
        _, m, s, fr, r = t
        return run_alarm(client, m, s, fr, r)

    done = 0
    with ThreadPoolExecutor(max_workers=8) as pool:
        futs = {pool.submit(dispatch, t): t for t in tasks}
        for f in as_completed(futs):
            try:
                f.result(); done += 1
            except BudgetExceededError:
                print(f"!! budget ceiling reached at {done}/{len(tasks)} — stopping (data kept)", flush=True)
                break
            except Exception as exc:  # noqa: BLE001
                tt = futs[f]
                print(f"  ! {tt[0]}:{tt[1].split('/')[-1]}: {type(exc).__name__}: {str(exc)[:60]}", flush=True)
            if done % 100 == 0:
                print(f"  {done}/{len(tasks)} | ${client.guard.total:.3f}", flush=True)
    print(client.guard.report())
    client.close()


if __name__ == "__main__":
    main()
