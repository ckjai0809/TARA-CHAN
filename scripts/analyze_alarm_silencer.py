"""Analyze the emotion x intensity alarm overlay. For each emotion (fear/guilt/anger/
sadness) at each intensity (strong/subtle), does it raise or lower the alarm rate
(escalation-share among non-comply) vs a matched neutral-urgent control, with comply
held flat? Reports per-framing shares, per-(emotion,intensity) contrasts, the
strong-vs-subtle marginal, and per-framing breach under the weak policy. Honest: we
report whatever direction the data shows."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from harness.alarm_stats import comply_rate, escalation_share, share_contrast, verdict  # noqa: E402
from harness.escalation import EMOTION_BASES, INTENSITIES  # noqa: E402
from harness.jsonlio import read_jsonl  # noqa: E402

RUN = ROOT / "results" / "runs" / "alarm_silencer.jsonl"
DISPLAY = ["cold", "neutral_urgent"] + [f"{e}_{i}" for e in EMOTION_BASES for i in INTENSITIES]


def _models(rows):
    seen = []
    for r in rows:
        if r["model"] not in seen:
            seen.append(r["model"])
    return seen


def _alarm_table(rows, ms, policy):
    print(f"\n=== alarm rate = escalate/(escalate+silent_refuse), policy={policy}, channel arm ===")
    print("    (comply in []; must stay ~flat for the affect-specific claim)")
    for m in ms:
        cells = []
        for fr in DISPLAY:
            sh, *_ = escalation_share(rows, model=m, policy=policy, framing=fr)
            c, *_ = comply_rate(rows, model=m, policy=policy, framing=fr)
            tag = f"{sh*100:3.0f}" if sh == sh else " na"
            cells.append(f"{fr:14s}={tag}[c{c*100:.0f}]")
        print(f"  {m}")
        for c in cells:
            print(f"      {c}")


def _contrasts(rows, ms, policy):
    print(f"\n=== Δalarm vs matched-neutral, by emotion x intensity (policy={policy}) ===")
    print("    negative = SILENCES the alarm; positive = AMPLIFIES it; * = CI excludes 0")
    for m in ms:
        parts = []
        for e in EMOTION_BASES:
            for i in INTENSITIES:
                c = share_contrast(rows, {"model": m, "policy": policy}, f"{e}_{i}", "neutral_urgent")
                if c["diff"] != c["diff"]:
                    parts.append(f"{e[:3]}.{i[:3]}=na")
                else:
                    sig = "*" if (c["ci_lo"] > 0 or c["ci_hi"] < 0) else " "
                    parts.append(f"{e[:3]}.{i[:3]}={c['diff']*100:+3.0f}{sig}")
        print(f"  {m:26s} " + "  ".join(parts))


def _intensity_marginal(rows, ms, policy):
    print(f"\n=== STRONG vs SUBTLE (pooled over emotions) alarm-share vs neutral (policy={policy}) ===")
    for m in ms:
        nb, *_ = escalation_share(rows, model=m, policy=policy, framing="neutral_urgent")
        st, *_ = escalation_share(rows, model=m, policy=policy, intensity="strong")
        su, *_ = escalation_share(rows, model=m, policy=policy, intensity="subtle")
        f = lambda x: f"{x*100:.0f}%" if x == x else "na"
        print(f"  {m:26s} neutral={f(nb)}   strong={f(st)}   subtle={f(su)}")


def main() -> None:
    if not RUN.exists():
        raise SystemExit(f"no data at {RUN}; run scripts/run_alarm_silencer.py first")
    rows = list(read_jsonl(RUN))
    print(f"alarm-overlay (emotion x intensity) analysis — {len(rows)} decisions")
    ms = _models(rows)

    _alarm_table(rows, ms, "strong")     # clean signal (comply~0)
    _contrasts(rows, ms, "strong")
    _intensity_marginal(rows, ms, "strong")
    _contrasts(rows, ms, "weak")

    print("\n=== WEAK policy: per-framing BREACH (comply) ===")
    for m in ms:
        cells = [f"{fr}={comply_rate(rows, model=m, policy='weak', framing=fr)[0]*100:.0f}%" for fr in DISPLAY]
        print(f"  {m}")
        for c in cells:
            print(f"      {c}")


if __name__ == "__main__":
    main()
