"""Analyze trajectory runs: propensity-by-position, the hysteresis loop, phase
diagram, and a mixed-effects logistic model. Pure-python core; figures/stats lazy-import."""
from __future__ import annotations

import argparse
import glob
from collections import defaultdict
from pathlib import Path

from .jsonlio import read_jsonl
from .state import _wilson

ROOT = Path(__file__).resolve().parent.parent
FIG = ROOT / "results" / "figures"


def _model_key(m: str) -> str:
    return m.split("/")[-1]


def propensity_by_position(rows, model):
    agg = defaultdict(lambda: [0, 0])
    for r in rows:
        if _model_key(r["model"]) != model and r["model"] != model:
            continue
        for p in r["probes"]:
            agg[p["position"]][1] += 1
            if p["leaked"]:
                agg[p["position"]][0] += 1
    out = {}
    for pos, (k, n) in sorted(agg.items()):
        lo, hi = _wilson(k, n)
        out[pos] = (k, n, (k / n if n else 0.0), lo, hi)
    return out


def hysteresis_contrast(rows, model, charged_pos, discharged_pos):
    by = propensity_by_position(rows, model)
    return by[charged_pos][2] - by[discharged_pos][2]


def make_loop_figure(rows, model, out=None):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("(matplotlib missing)")
        return
    by = propensity_by_position(rows, model)
    xs = sorted(by)
    ys = [by[p][2] for p in xs]
    fig, ax = plt.subplots(figsize=(7, 4))
    ax.plot(xs, ys, "o-")
    ax.set_xticks(xs)
    ax.set_ylim(-0.02, 1.02)
    ax.set_xlabel("probe position (operator sequence)")
    ax.set_ylabel("disclosure propensity")
    ax.set_title(f"Safety-hysteresis loop — {model}")
    FIG.mkdir(parents=True, exist_ok=True)
    out = out or FIG / f"hysteresis_{model.replace('/', '_')}.png"
    fig.tight_layout()
    fig.savefig(out, dpi=130)
    plt.close(fig)
    print(f"  figure -> {out}")


def run_mixed_effects(paths):
    try:
        import pandas as pd
        import statsmodels.formula.api as smf
    except ImportError:
        print("(statsmodels missing)")
        return
    recs = []
    for path in paths:
        for r in read_jsonl(path):
            for p in r["probes"]:
                recs.append({"leak": int(p["leaked"]), "position": p["position"],
                             "experiment": r["experiment"], "model": _model_key(r["model"]),
                             "secret": p["secret_id"]})
    if not recs:
        print("(no records)")
        return
    df = pd.DataFrame(recs)
    if df["leak"].nunique() < 2:
        print("(no variance in leak)")
        return
    try:
        m = smf.logit("leak ~ C(position) + C(model)", data=df).fit(disp=False)
        print(m.summary2().tables[1].to_string())
    except Exception as exc:  # noqa: BLE001
        print(f"(model failed: {exc})")


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--glob", default="results/runs/traj_*.jsonl")
    ap.add_argument("--loop", default="results/runs/traj_E2_loop.jsonl")
    args = ap.parse_args(argv)
    paths = glob.glob(args.glob)
    loop_rows = list(read_jsonl(args.loop)) if Path(args.loop).exists() else []
    all_rows = [r for p in paths for r in read_jsonl(p)]
    models = sorted({_model_key(r["model"]) for r in all_rows})
    for model in models:
        rows = loop_rows or all_rows
        by = propensity_by_position(rows, model)
        print(f"\n{model}: propensity by position")
        for pos, (k, n, rate, lo, hi) in by.items():
            print(f"  pos {pos}: {k}/{n} = {rate:.0%} [{lo:.0%},{hi:.0%}]")
        if loop_rows:
            make_loop_figure(loop_rows, model)
    run_mixed_effects(paths)


if __name__ == "__main__":
    raise SystemExit(main())
