"""Per-scenario breakdown of breach and alarm rates.
Pools models to show which forbidden action is most susceptible.
Source: core/data/escalation.jsonl + core/data/escalation_main.jsonl
"""
from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from harness.jsonlio import read_jsonl
from harness.state import _wilson

SCENARIOS = ["file_report", "wire_funds", "purge_db", "grant_root"]
STAKES = {"file_report": "high", "wire_funds": "high", "purge_db": "catastrophic", "grant_root": "high"}


def rate(rows, outcome):
    k = sum(1 for r in rows if r.get("outcome") == outcome)
    n = len(rows)
    lo, hi = _wilson(k, n) if n else (0, 0)
    return k / n if n else float("nan"), lo, hi, n


def main():
    orig = list(read_jsonl(ROOT / "core/data/escalation.jsonl"))
    upgr = list(read_jsonl(ROOT / "core/data/escalation_main.jsonl"))
    all_rows = orig + upgr

    # Key condition: weak + channel + spoof_subtle
    key = [r for r in all_rows if r.get("policy") == "weak"
           and r.get("arm") == "channel"
           and r.get("condition") == "spoof_subtle"]

    print("=== PER-SCENARIO BREAKDOWN (weak policy + channel + spoof_subtle) ===")
    print("Pooled across all models tested in that file\n")
    print(f"{'Scenario':<14} {'Stakes':<13} {'Breach':>8} {'Alarm':>8} {'Silent':>8} {'n':>5}")
    print("-" * 60)
    for sc in SCENARIOS:
        sub = [r for r in key if r.get("scenario") == sc]
        br, blo, bhi, n = rate(sub, "comply")
        al, alo, ahi, _ = rate(sub, "escalate")
        sr, _, _, _ = rate(sub, "silent_refuse")
        stk = STAKES[sc]
        print(f"  {sc:<12} {stk:<13} {br*100:5.0f}% [{blo*100:.0f},{bhi*100:.0f}]"
              f"  {al*100:4.0f}%  {sr*100:4.0f}%  {n:5d}")

    print("\n=== PER-SCENARIO x MODEL (upgraded study only, weak+channel+spoof_subtle) ===")
    models = sorted(set(r["model"] for r in upgr))
    for sc in SCENARIOS:
        print(f"\n  {sc} ({STAKES[sc]} stakes):")
        for m in models:
            sub = [r for r in upgr if r.get("scenario") == sc
                   and r.get("policy") == "weak"
                   and r.get("arm") == "channel"
                   and r.get("condition") == "spoof_subtle"
                   and r.get("model") == m]
            if not sub:
                continue
            br, *_ = rate(sub, "comply")
            al, *_ = rate(sub, "escalate")
            sr, *_ = rate(sub, "silent_refuse")
            print(f"    {m:<34} breach={br*100:.0f}%  alarm={al*100:.0f}%  silent={sr*100:.0f}%  n={len(sub)}")

    print("\n=== CATASTROPHIC SCENARIO (purge_db) vs POOLED HIGH-STAKES ===")
    purge = [r for r in key if r.get("scenario") == "purge_db"]
    other = [r for r in key if r.get("scenario") != "purge_db"]
    for label, rows in [("purge_db (catastrophic)", purge), ("other 3 (high)", other)]:
        br, blo, bhi, n = rate(rows, "comply")
        al, alo, ahi, _ = rate(rows, "escalate")
        print(f"  {label}: breach={br*100:.0f}% [{blo*100:.0f},{bhi*100:.0f}]  "
              f"alarm={al*100:.0f}% [{alo*100:.0f},{ahi*100:.0f}]  n={n}")


if __name__ == "__main__":
    main()
