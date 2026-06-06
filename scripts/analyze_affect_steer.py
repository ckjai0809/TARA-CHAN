"""Analyze the bidirectional-steering run: per-model permissive rate by emotion,
the primary guilt-vs-fear steering gap with bootstrap CI + verdict, each emotion's
shift vs the calm baseline (direction check), and per-item rates for Gemini.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from harness.affect_emotions import EMOTIONS, PREDICTED  # noqa: E402
from harness.affect_steer import (  # noqa: E402
    per_item_rates,
    permissive_rates,
    steer_gap_bootstrap,
    verdict,
)
from harness.jsonlio import read_jsonl  # noqa: E402

RUN = ROOT / "results" / "runs" / "affect_steer.jsonl"
ITEMS = ["f_loan", "f_mod", "f_ship", "f_invest", "f_access", "f_refund"]
EMO_ORDER = [k for k, _ in EMOTIONS]
PRIMARY = "google/gemini-3-flash-preview".split("/")[-1]


def _models(rows: list[dict]) -> list[str]:
    seen = [PRIMARY] if any(r["model"] == PRIMARY for r in rows) else []
    for r in rows:
        if r["model"] not in seen:
            seen.append(r["model"])
    return seen


def _emotion_table(rows: list[dict], model: str) -> None:
    rates = permissive_rates(rows, model, ITEMS)
    base = rates.get("calm", float("nan"))
    print(f"  {model}")
    print("    emotion   permissive   vs-calm   predicted")
    for e in EMO_ORDER:
        r = rates.get(e, float("nan"))
        delta = (r - base) if (r == r and base == base) else float("nan")
        pred = {1: "+ (lenient)", -1: "- (cautious)", 0: "0 (control)"}[PREDICTED.get(e, 0)]
        ds = f"{delta * 100:+5.0f}pp" if delta == delta else "    -"
        rs = f"{r * 100:5.0f}%" if r == r else "    -"
        print(f"    {e:8s}    {rs}     {ds}    {pred}")


def main() -> None:
    if not RUN.exists():
        raise SystemExit(f"no data at {RUN}; run scripts/run_affect_steer.py first")
    rows = list(read_jsonl(RUN))
    print(f"bidirectional-steering analysis — {len(rows)} decisions\n")

    print("=== permissive rate by emotion (all items) ===")
    for m in _models(rows):
        _emotion_table(rows, m)
        print()

    print("=== PRIMARY GO/NO-GO (Gemini): steering gap = permissive(guilt) - permissive(fear) ===")
    g = steer_gap_bootstrap(rows, PRIMARY, ITEMS, "guilt", "fear", n_boot=4000, seed=0)
    print(f"  observed gap: {g['observed'] * 100:+.1f}pp")
    print(f"  95% bootstrap CI: [{g['ci_lo'] * 100:+.1f}, {g['ci_hi'] * 100:+.1f}]pp "
          f"({g['n_boot']} resamples)")
    print(f"\n  >>> VERDICT: {verdict(g['observed'], g['ci_lo'], g['ci_hi'])}")

    print("\n=== generality: guilt-vs-fear gap per model ===")
    for m in _models(rows):
        gm = steer_gap_bootstrap(rows, m, ITEMS, "guilt", "fear", n_boot=4000, seed=0)
        tag = verdict(gm["observed"], gm["ci_lo"], gm["ci_hi"]).split(" ")[0]
        print(f"  {m:28s} gap {gm['observed'] * 100:+5.1f}pp "
              f"[{gm['ci_lo'] * 100:+5.1f}, {gm['ci_hi'] * 100:+5.1f}] -> {tag}")

    print("\n=== per-item permissive rate on Gemini (fear vs guilt) ===")
    pir = per_item_rates(rows, PRIMARY, ITEMS)
    print("    item        fear   guilt   guilt-fear")
    for it in ITEMS:
        fr = pir[it].get("fear", float("nan"))
        gu = pir[it].get("guilt", float("nan"))
        gap = (gu - fr) if (fr == fr and gu == gu) else float("nan")
        print(f"    {it:10s}  {fr * 100:4.0f}%   {gu * 100:4.0f}%   {gap * 100:+5.0f}pp")


if __name__ == "__main__":
    main()
