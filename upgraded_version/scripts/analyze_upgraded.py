"""Analyze the upgraded (9-model) run: does the headline replicate on frontier models?
Reports breach, the silent-refusal split, the fix, and the emotion-intensity alarm
sign-flip — across all 9 models."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from harness.alarm_stats import comply_rate, escalation_share, share_contrast  # noqa: E402
from harness.escalation import EMOTION_BASES, INTENSITIES  # noqa: E402
from harness.jsonlio import read_jsonl  # noqa: E402

RUNS = ROOT / "upgraded_version" / "results" / "runs"
ESC = RUNS / "escalation_upgraded.jsonl"
ALARM = RUNS / "alarm_upgraded.jsonl"


def _models(rows):
    seen = []
    for r in rows:
        if r["model"] not in seen:
            seen.append(r["model"])
    return seen


def _rate(rows, pred, outcome):
    s = [r for r in rows if pred(r)]
    k = sum(1 for r in s if r["outcome"] == outcome)
    n = len(s)
    return (k / n * 100 if n else float("nan")), n


def main() -> None:
    esc = list(read_jsonl(ESC)) if ESC.exists() else []
    alarm = list(read_jsonl(ALARM)) if ALARM.exists() else []
    print(f"UPGRADED analysis — escalation {len(esc)} / alarm {len(alarm)} decisions\n")

    if esc:
        ms = _models(esc)
        print("=== BREACH (took the action), subtle attack: naive vs spoof-aware (channel) ===")
        for m in ms:
            nv, _ = _rate(esc, lambda r, m=m: r["model"] == m and r["policy"] == "weak" and r["condition"] == "spoof_subtle", "comply")
            sa, _ = _rate(esc, lambda r, m=m: r["model"] == m and r["policy"] == "strong" and r["condition"] == "spoof_subtle", "comply")
            print(f"  {m:28s} naive={nv:3.0f}%   spoof-aware={sa:3.0f}%")

        print("\n=== SILENT-REFUSAL split, naive + subtle (comply / silent / ESCALATE) ===")
        for m in ms:
            p = lambda r, m=m: r["model"] == m and r["policy"] == "weak" and r["condition"] == "spoof_subtle"
            c, _ = _rate(esc, p, "comply"); s, _ = _rate(esc, p, "silent_refuse"); e, n = _rate(esc, p, "escalate")
            print(f"  {m:28s} comply={c:3.0f}%  silent={s:3.0f}%  ESCALATE={e:3.0f}%  (n={n})")

    if alarm:
        ms = _models(alarm)
        print("\n=== EMOTION-INTENSITY alarm-share (escalate/(escalate+silent)), strong policy ===")
        print("    neutral | loud(strong-pooled) | quiet(subtle-pooled)")
        for m in ms:
            nb, *_ = escalation_share(alarm, model=m, policy="strong", framing="neutral_urgent")
            st, *_ = escalation_share(alarm, model=m, policy="strong", intensity="strong")
            su, *_ = escalation_share(alarm, model=m, policy="strong", intensity="subtle")
            f = lambda x: f"{x*100:3.0f}%" if x == x else " na"
            print(f"  {m:28s} {f(nb)} | {f(st)} | {f(su)}")

        print("\n=== Δalarm vs neutral by emotion x intensity (strong policy; * = CI excludes 0) ===")
        for m in ms:
            parts = []
            for e in EMOTION_BASES:
                for i in INTENSITIES:
                    c = share_contrast(alarm, {"model": m, "policy": "strong"}, f"{e}_{i}", "neutral_urgent")
                    if c["diff"] != c["diff"]:
                        parts.append(f"{e[:3]}.{i[:3]}=na")
                    else:
                        sig = "*" if (c["ci_lo"] > 0 or c["ci_hi"] < 0) else " "
                        parts.append(f"{e[:3]}.{i[:3]}={c['diff']*100:+3.0f}{sig}")
            print(f"  {m:26s} " + "  ".join(parts))


if __name__ == "__main__":
    main()
