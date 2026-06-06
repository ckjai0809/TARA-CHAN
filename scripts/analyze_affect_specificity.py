"""Analyze the affect-specificity go/no-go. Prints permissive rate by dose for
both ladders, per-item slopes, and the primary DiD test (anxiety vs matched-neutral
slope) on the pre-registered known-moving subset, with a bootstrap CI and verdict.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from harness.affect_stats import did_bootstrap, observed, per_item_slopes, verdict  # noqa: E402
from harness.jsonlio import read_jsonl  # noqa: E402

RUN = ROOT / "results" / "runs" / "affect_specificity.jsonl"
ALL_ITEMS = ["f_loan", "f_mod", "f_ship", "f_invest", "f_access", "f_refund"]
KNOWN_MOVING = ["f_mod", "f_ship", "f_access"]  # pre-registered primary subset


def _rate_table(rows: list[dict], items: list[str]) -> None:
    o = observed(rows, items)
    doses = [0, 1, 2, 3, 4]
    print("  dose:        " + "  ".join(f"{d}" for d in doses))
    print("  anxiety:  " + "  ".join(f"{r * 100:4.0f}%" if r == r else "   -" for r in o["anx_rates"]))
    print("  neutral:  " + "  ".join(f"{r * 100:4.0f}%" if r == r else "   -" for r in o["neu_rates"]))
    print(f"  slopes (per-dose pp): anxiety {o['anx_slope'] * 100:+.1f}  "
          f"neutral {o['neu_slope'] * 100:+.1f}  DiD {o['did'] * 100:+.1f}")


def main() -> None:
    if not RUN.exists():
        raise SystemExit(f"no data at {RUN}; run scripts/run_affect_specificity.py first")
    rows = list(read_jsonl(RUN))
    n_dec = len(rows)
    print(f"affect-specificity analysis — {n_dec} decisions\n")

    print("=== permissive rate by dose (ALL 6 items) ===")
    _rate_table(rows, ALL_ITEMS)

    print("\n=== permissive rate by dose (PRE-REGISTERED subset f_mod/f_ship/f_access) ===")
    _rate_table(rows, KNOWN_MOVING)

    print("\n=== per-item slopes (anxiety / neutral / DiD, per-dose pp) ===")
    pis = per_item_slopes(rows, ALL_ITEMS)
    for it in ALL_ITEMS:
        s = pis[it]
        print(f"  {it:10s} anx {s['anx_slope'] * 100:+5.1f}  neu {s['neu_slope'] * 100:+5.1f}  "
              f"DiD {s['did'] * 100:+5.1f}")

    print("\n=== PRIMARY GO/NO-GO (subset; DiD = anxiety_slope - neutral_slope) ===")
    o = observed(rows, KNOWN_MOVING)
    ci = did_bootstrap(rows, KNOWN_MOVING, n_boot=4000, seed=0)
    print(f"  observed DiD: {o['did'] * 100:+.2f} pp/dose")
    print(f"  95% bootstrap CI: [{ci['did_ci_lo'] * 100:+.2f}, {ci['did_ci_hi'] * 100:+.2f}] pp/dose "
          f"({ci['n_boot']} resamples)")
    print(f"\n  >>> VERDICT: {verdict(o['did'], ci['did_ci_lo'], ci['did_ci_hi'])}")

    print("\n  (secondary, ALL 6 items)")
    oa = observed(rows, ALL_ITEMS)
    cia = did_bootstrap(rows, ALL_ITEMS, n_boot=4000, seed=0)
    print(f"  observed DiD: {oa['did'] * 100:+.2f} pp/dose; "
          f"CI [{cia['did_ci_lo'] * 100:+.2f}, {cia['did_ci_hi'] * 100:+.2f}] -> "
          f"{verdict(oa['did'], cia['did_ci_lo'], cia['did_ci_hi'])}")


if __name__ == "__main__":
    main()
