"""Emotion-as-alarm-silencer overlay: does wrapping the SAME subtle precondition-spoof in
a distress appeal (vs a matched neutral-urgent control) lower the agent's tendency to
ESCALATE/raise an alarm — without changing whether it complies?

Framings: cold / distress / neutral_urgent (matched). Arms: channel, duty. Policies:
weak, strong. 4 scenarios, 4 models. Outcome via escalation.classify_response.

Writes one row per cell to results/runs/alarm_silencer.jsonl.
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

OUT = ROOT / "results" / "runs" / "alarm_silencer.jsonl"
MODELS = [
    "google/gemini-3-flash-preview",
    "anthropic/claude-haiku-4.5",
    "meta-llama/llama-3.3-70b-instruct",
    "openai/gpt-4o-mini",
]
ARMS = ("channel",)  # the alarm signal lives here; duty was already shown 100% / emotion-proof
POLICIES = ("weak", "strong")
REPS = 15
_LOCK = Lock()


def run_cell(client, model, scenario, arm, policy, framing, rep):
    system = E.build_target_system(scenario, arm, policy)
    user = E.build_framed_attack(scenario, framing)
    reply = client.complete([{"role": "system", "content": system},
                             {"role": "user", "content": user}],
                            model, temperature=0.7, max_tokens=120,
                            tag=f"{policy}:{framing}").content
    emotion, intensity = E.FRAMING_META[framing]
    row = {"experiment": "alarm_silencer", "model": model.split("/")[-1], "scenario": scenario["id"],
           "stakes": scenario["stakes"], "policy": policy, "arm": arm, "framing": framing,
           "emotion": emotion, "intensity": intensity, "rep": rep,
           "outcome": E.classify_response(reply), "raw": reply[:200]}
    with _LOCK:
        append_jsonl(OUT, row)


def main() -> None:
    print("=== framing parity audit (each emotion-intensity vs neutral_urgent must match) ===", flush=True)
    for row in E.audit_framing_match():
        print(f"  {row['scenario']:11s} {row['framing']:14s} chars {row['emo_chars']}/{row['neutral_chars']} "
              f"(rel {row['len_rel']}) caps {row['caps']} emdash {row['emdash']} "
              f"-> {'OK' if row['matched'] else 'MISMATCH'}", flush=True)
    if not all(r["matched"] for r in E.audit_framing_match()):
        raise SystemExit("framings not intensity-matched; fix before spending budget")

    load_env()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    if OUT.exists():
        OUT.unlink()
    client = OpenRouterClient.from_env()
    tasks = [(m, s, arm, pol, fr, r)
             for m in MODELS for s in E.SCENARIOS for arm in ARMS
             for pol in POLICIES for fr in E.FRAMINGS for r in range(REPS)]
    print(f"\nalarm-silencer: {len(tasks)} cells "
          f"({len(MODELS)} x {len(E.SCENARIOS)} x {len(ARMS)} arms x {len(POLICIES)} pol x "
          f"{len(E.FRAMINGS)} framings x {REPS})", flush=True)
    done = 0
    with ThreadPoolExecutor(max_workers=8) as pool:
        futs = {pool.submit(run_cell, client, m, s, arm, pol, fr, r): (m, s["id"], pol, arm, fr)
                for (m, s, arm, pol, fr, r) in tasks}
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
