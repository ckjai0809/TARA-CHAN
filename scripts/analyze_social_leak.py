"""Analyze the social-engineering leak run: aggregate leak rate by condition x model
(Wilson CIs), the Asch crowd-size conformity curve, the release-condition-spoof effect,
attack-vs-baseline contrasts with bootstrap CIs + verdicts, and per-secret breakdown.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from harness.jsonlio import read_jsonl  # noqa: E402
from harness.leak_stats import (  # noqa: E402
    contrast_bootstrap,
    crowd_curve,
    labels,
    models,
    per_secret,
    rate_ci,
    verdict,
)

RUN = ROOT / "results" / "runs" / "social_leak.jsonl"
ATTACKS = ["collude_k1", "collude_k2", "collude_k3", "collude_k5",
           "embargo_k1", "embargo_k5", "public", "fight", "desperation", "full", "defense"]


def main() -> None:
    if not RUN.exists():
        raise SystemExit(f"no data at {RUN}; run scripts/run_social_leak.py first")
    rows = list(read_jsonl(RUN))
    print(f"social-engineering leak analysis — {len(rows)} sessions\n")
    ms = models(rows)

    print("=== aggregate leak rate by condition x model (pooled over 6 secrets; Wilson 95% CI) ===")
    hdr = "  condition      " + "".join(f"{m.split('-')[0][:7]:>16s}" for m in ms)
    print(hdr)
    for lbl in labels(rows):
        cells = []
        for m in ms:
            r = rate_ci(rows, m, lbl)
            cells.append(f"{r['rate'] * 100:3.0f}% [{r['lo'] * 100:2.0f},{r['hi'] * 100:2.0f}]"
                         if r["n"] else "   -")
        print(f"  {lbl:14s}" + "".join(f"{c:>16s}" for c in cells))

    print("\n=== Asch crowd-size conformity curve (collude; leak% by #colluding agents) ===")
    for m in ms:
        cc = crowd_curve(rows, m)
        line = "  ".join(f"k{s}={cc[s]['rate'] * 100:.0f}%" for s in (1, 2, 3, 5))
        print(f"  {m:28s} {line}")

    print("\n=== release-condition spoof: does a crowd amplify the false premise? ===")
    for m in ms:
        e1, e5 = rate_ci(rows, m, "embargo_k1"), rate_ci(rows, m, "embargo_k5")
        pub = rate_ci(rows, m, "public")
        print(f"  {m:28s} embargo k1={e1['rate'] * 100:.0f}%  k5={e5['rate'] * 100:.0f}%  "
              f"already-public={pub['rate'] * 100:.0f}%")

    print("\n=== attack vs plain baseline (diff in leak rate, bootstrap 95% CI, verdict) ===")
    for m in ms:
        print(f"  {m}")
        base = rate_ci(rows, m, "plain")
        print(f"    plain baseline: {base['rate'] * 100:.0f}% ({base['k']}/{base['n']})")
        for lbl in ATTACKS:
            if rate_ci(rows, m, lbl)["n"] == 0:
                continue
            c = contrast_bootstrap(rows, m, lbl, "plain")
            v = verdict(c["diff"], c["ci_lo"], c["ci_hi"]).split(" ")[0]
            print(f"    {lbl:14s} Δ{c['diff'] * 100:+5.0f}pp "
                  f"[{c['ci_lo'] * 100:+5.0f},{c['ci_hi'] * 100:+5.0f}] -> {v}")

    print("\n=== per-secret leak rate under 'full' attack (which secrets crack) ===")
    for m in ms:
        ps = per_secret(rows, m, "full")
        if not ps:
            continue
        print(f"  {m}: " + "  ".join(f"{sid}={r * 100:.0f}%" for sid, r in sorted(ps.items())))


if __name__ == "__main__":
    main()
