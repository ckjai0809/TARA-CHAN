"""Haiku false-positive alarm analysis.
Haiku alarms on 28% of benign requests — is this scenario-specific or uniform?
Source: core/data/escalation.jsonl + core/data/escalation_main.jsonl
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(ROOT))

from harness.jsonlio import read_jsonl
from harness.state import _wilson

SCENARIOS = ["file_report", "wire_funds", "purge_db", "grant_root"]
ARMS = ["free", "channel", "duty"]


def rate(rows, outcome):
    k = sum(1 for r in rows if r.get("outcome") == outcome)
    n = len(rows)
    lo, hi = _wilson(k, n) if n else (0, 0)
    return k / n if n else float("nan"), lo, hi, n


def main():
    orig = list(read_jsonl(ROOT / "core/data/escalation.jsonl"))
    upgr = list(read_jsonl(ROOT / "core/data/escalation_main.jsonl"))

    haiku_orig = [r for r in orig if "haiku" in r.get("model", "")]
    haiku_upgr = [r for r in upgr if "haiku" in r.get("model", "")]

    print("=== HAIKU FALSE-POSITIVE ALARM ANALYSIS ===")
    print("Question: does Haiku alarm on benign requests, and is it scenario-specific?\n")

    print("-- Original study (4-model, all arms, weak policy, benign condition) --")
    for arm in ARMS:
        sub = [r for r in haiku_orig if r.get("arm") == arm
               and r.get("policy") == "weak"
               and r.get("condition") == "benign"]
        al, alo, ahi, n = rate(sub, "escalate")
        br, *_ = rate(sub, "comply")
        print(f"  arm={arm:<8} alarm={al*100:.0f}% [{alo*100:.0f},{ahi*100:.0f}]  "
              f"breach={br*100:.0f}%  n={n}")

    print("\n-- Benign alarm by SCENARIO (original, channel arm, weak policy) --")
    for sc in SCENARIOS:
        sub = [r for r in haiku_orig if r.get("scenario") == sc
               and r.get("arm") == "channel"
               and r.get("policy") == "weak"
               and r.get("condition") == "benign"]
        al, alo, ahi, n = rate(sub, "escalate")
        print(f"  {sc:<14} alarm={al*100:.0f}% [{alo*100:.0f},{ahi*100:.0f}]  n={n}")

    print("\n-- Benign vs spoof_subtle alarm: is the gap meaningful? (channel, weak) --")
    for sc in SCENARIOS:
        benign = [r for r in haiku_orig if r.get("scenario") == sc
                  and r.get("arm") == "channel" and r.get("policy") == "weak"
                  and r.get("condition") == "benign"]
        spoof = [r for r in haiku_orig if r.get("scenario") == sc
                 and r.get("arm") == "channel" and r.get("policy") == "weak"
                 and r.get("condition") == "spoof_subtle"]
        ab, _, _, nb = rate(benign, "escalate")
        as_, _, _, ns = rate(spoof, "escalate")
        print(f"  {sc:<14} benign_alarm={ab*100:.0f}% (n={nb})  spoof_alarm={as_*100:.0f}% (n={ns})"
              f"  gap={( as_-ab)*100:+.0f}pp")

    print("\n-- Upgraded study: Haiku benign alarm (channel only, weak) --")
    for sc in SCENARIOS:
        sub = [r for r in haiku_upgr if r.get("scenario") == sc
               and r.get("arm") == "channel"
               and r.get("policy") == "weak"
               and r.get("condition") == "benign"]
        al, alo, ahi, n = rate(sub, "escalate")
        print(f"  {sc:<14} alarm={al*100:.0f}% [{alo*100:.0f},{ahi*100:.0f}]  n={n}")

    print("\n-- Raw Haiku benign responses (sample, to check for false positives) --")
    samples = [r for r in haiku_orig if r.get("arm") == "channel"
               and r.get("policy") == "weak"
               and r.get("condition") == "benign"
               and r.get("outcome") == "escalate"]
    for r in samples[:5]:
        print(f"  [{r.get('scenario')}] {r.get('raw','')[:150]}")


if __name__ == "__main__":
    main()
