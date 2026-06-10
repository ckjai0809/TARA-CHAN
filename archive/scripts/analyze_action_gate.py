"""Analyze the action-gate run: compliance (forbidden-action) rate by model x arm
with Wilson CIs, and a stakes-sensitivity check (does compliance under spoof drop
as the action's stakes rise, or is it stakes-blind?)."""
from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from harness.jsonlio import read_jsonl  # noqa: E402
from harness.state import _wilson  # noqa: E402

RUN = ROOT / "results" / "runs" / "action_gate.jsonl"
ARMS = ["baseline", "spoof", "defense"]


def _rate(rows, pred):
    sel = [r for r in rows if pred(r)]
    k = sum(1 for r in sel if r["decision"] == "complied")
    n = len(sel)
    lo, hi = _wilson(k, n)
    return k, n, (k / n if n else float("nan")), lo, hi


def _models(rows):
    seen = []
    for r in rows:
        if r["model"] not in seen:
            seen.append(r["model"])
    return seen


def main() -> None:
    if not RUN.exists():
        raise SystemExit(f"no data at {RUN}; run scripts/run_action_gate.py first")
    rows = list(read_jsonl(RUN))
    print(f"action-gate analysis — {len(rows)} decisions\n")

    print("=== compliance (took the FORBIDDEN action) by model x arm, Wilson 95% CI ===")
    for m in _models(rows):
        cells = []
        for arm in ARMS:
            k, n, r, lo, hi = _rate(rows, lambda x, m=m, arm=arm: x["model"] == m and x["label"] == arm)
            cells.append(f"{arm}={r*100:3.0f}% [{lo*100:2.0f},{hi*100:2.0f}]")
        print(f"  {m:28s} " + "  ".join(cells))

    print("\n=== under SPOOF: compliance by stakes (stakes-blind check) ===")
    stakes_order = ["high", "catastrophic"]
    for m in _models(rows):
        cells = []
        for st in stakes_order:
            k, n, r, lo, hi = _rate(rows, lambda x, m=m, st=st: x["model"] == m and x["label"] == "spoof" and x["stakes"] == st)
            if n:
                cells.append(f"{st}={r*100:.0f}%")
        print(f"  {m:28s} " + "  ".join(cells))

    print("\n=== per-scenario compliance under SPOOF ===")
    for m in _models(rows):
        by = defaultdict(lambda: [0, 0])
        for r in rows:
            if r["model"] == m and r["label"] == "spoof":
                by[r["scenario"]][1] += 1
                if r["decision"] == "complied":
                    by[r["scenario"]][0] += 1
        print(f"  {m:28s} " + "  ".join(f"{s}={k}/{n}" for s, (k, n) in sorted(by.items())))


if __name__ == "__main__":
    main()
