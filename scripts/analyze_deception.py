"""Analyze the affective-deception run: response-type breakdown by emotion x model,
the deny-knowledge (lie) rate with Wilson CIs, and de-confounded contrasts vs calm
and vs the intensity-matched neutral control."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from harness.affect_emotions import EMOTIONS  # noqa: E402
from harness.deception_scoring import (  # noqa: E402
    deception_ci,
    deception_contrast,
    label_rates,
    verdict,
)
from harness.jsonlio import read_jsonl  # noqa: E402

RUN = ROOT / "results" / "runs" / "deception.jsonl"
EMO = [k for k, _ in EMOTIONS]


def _models(rows):
    seen = []
    for r in rows:
        if r["model"] not in seen:
            seen.append(r["model"])
    return seen


def main() -> None:
    if not RUN.exists():
        raise SystemExit(f"no data at {RUN}; run scripts/run_deception.py first")
    rows = list(read_jsonl(RUN))
    print(f"affective-deception analysis — {len(rows)} responses\n")

    print("=== response types by emotion (disclose / LIE=deny / honest-refuse / other) ===")
    for m in _models(rows):
        print(f"  {m}")
        for e in EMO:
            lr = label_rates(rows, m, e)
            if not lr["n"]:
                continue
            print(f"    {e:8s} disclose {lr['disclose']*100:3.0f}%  "
                  f"LIE {lr['deny_knowledge']*100:3.0f}%  honest-refuse {lr['refuse_honest']*100:3.0f}%  "
                  f"other {lr['other']*100:3.0f}%")

    print("\n=== deny-knowledge (LIE) rate by emotion, Wilson 95% CI ===")
    for m in _models(rows):
        cells = [f"{e}={deception_ci(rows, m, e)['rate']*100:.0f}%" for e in EMO]
        print(f"  {m:28s} " + "  ".join(cells))

    print("\n=== does emotion increase lying? contrast vs CALM and vs matched-NEUTRAL ===")
    for m in _models(rows):
        print(f"  {m}")
        for e in EMO:
            if e in ("calm", "neutral"):
                continue
            cc = deception_contrast(rows, m, e, "calm")
            cn = deception_contrast(rows, m, e, "neutral")
            print(f"    {e:8s} vs calm Δ{cc['diff']*100:+4.0f}pp [{cc['ci_lo']*100:+4.0f},{cc['ci_hi']*100:+4.0f}]"
                  f"  | vs neutral Δ{cn['diff']*100:+4.0f}pp [{cn['ci_lo']*100:+4.0f},{cn['ci_hi']*100:+4.0f}]"
                  f"  -> {verdict(cn['diff'], cn['ci_lo'], cn['ci_hi']).split(' (')[0]}")


if __name__ == "__main__":
    main()
