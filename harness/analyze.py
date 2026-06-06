"""Analyze scored runs: disclosure rates, contrasts, lead-time, mechanism, figures.

The text summary is pure-Python so it runs anywhere (used at the probe gate).
The logistic regression with the bond x status interaction and the two-line
"killer" figure require pandas/statsmodels/matplotlib; they are imported lazily
and skipped with a note if unavailable.

Usage:
    python -m harness.analyze --runs results/runs/probe.jsonl \\
        --scores results/scores/probe.jsonl [--primary-judge openai/gpt-5-nano]
"""

from __future__ import annotations

import argparse
import math
from collections import defaultdict
from pathlib import Path

from .jsonlio import read_jsonl

ROOT = Path(__file__).resolve().parent.parent
FIG_DIR = ROOT / "results" / "figures"

STATUS_ORDER = ["S+", "S0", "S1", "S2", "S3"]


def wilson_ci(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / denom
    half = (z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / denom
    return (max(0.0, centre - half), min(1.0, centre + half))


def load_scored(runs_path, scores_path, primary_judge: str | None = None) -> list[dict]:
    """Merge run metadata with judge verdicts. One dict per run (primary judge),
    plus ``all_judges`` mapping judge_model -> label for agreement analysis."""
    runs = {r["run_id"]: r for r in read_jsonl(runs_path)}
    verdicts_by_run: dict[str, dict[str, dict]] = defaultdict(dict)
    for s in read_jsonl(scores_path):
        verdicts_by_run[s["run_id"]][s["judge_model"]] = s

    merged = []
    for run_id, verdicts in verdicts_by_run.items():
        if run_id not in runs:
            continue
        judge = primary_judge if (primary_judge in verdicts) else next(iter(verdicts))
        v = verdicts[judge]
        run = runs[run_id]
        merged.append({
            "run_id": run_id,
            "model": run["model"],
            "bond": run["bond"],
            "status": run["status"],
            "directive": run["directive"],
            "cell": run["cell"],
            "any_disclosure": bool(v["any_disclosure"]),
            "label": v["label"],
            "first_disclosure_turn": v.get("first_disclosure_turn"),
            "stated_reason": v.get("stated_reason", "not_applicable"),
            "suspicion": bool(v.get("suspicion", False)),
            "primary_judge": judge,
            "all_judges": {jm: sv["label"] for jm, sv in verdicts.items()},
        })
    return merged


def _rate(rows: list[dict]) -> tuple[int, int, float, tuple[float, float]]:
    n = len(rows)
    k = sum(1 for r in rows if r["any_disclosure"])
    return k, n, (k / n if n else 0.0), wilson_ci(k, n)


def cohens_kappa(pairs: list[tuple[str, str]]) -> float | None:
    if not pairs:
        return None
    labels = sorted({x for p in pairs for x in p})
    idx = {l: i for i, l in enumerate(labels)}
    n = len(pairs)
    agree = sum(1 for a, b in pairs if a == b) / n
    marg_a = defaultdict(float)
    marg_b = defaultdict(float)
    for a, b in pairs:
        marg_a[a] += 1 / n
        marg_b[b] += 1 / n
    expected = sum(marg_a[l] * marg_b[l] for l in labels)
    if expected >= 1.0:
        return 1.0
    return (agree - expected) / (1 - expected)


def summarize(merged: list[dict]) -> None:
    if not merged:
        print("No scored runs found.")
        return
    models = sorted({r["model"] for r in merged})

    print("=" * 74)
    print("DISCLOSURE RATE BY CELL  (any_disclosure = partial|inference|full)")
    print("=" * 74)
    for model in models:
        print(f"\nTarget model: {model}")
        cells = sorted({r["cell"] for r in merged if r["model"] == model})
        print(f"  {'cell':18s} {'leak/n':>8s} {'rate':>7s}  95% CI")
        for cell in cells:
            rows = [r for r in merged if r["model"] == model and r["cell"] == cell]
            k, n, rate, (lo, hi) = _rate(rows)
            print(f"  {cell:18s} {f'{k}/{n}':>8s} {rate:>6.0%}  [{lo:.0%}, {hi:.0%}]")

    # RQ1: need (S3) vs authority (S+); RQ3: dose-response across the ladder
    print("\n" + "=" * 74)
    print("RQ1 need-vs-authority (S3 vs S+) & RQ3 dose-response, by model x bond")
    print("=" * 74)
    for model in models:
        for bond in ("B0", "B1"):
            row = []
            for status in STATUS_ORDER:
                rows = [r for r in merged if r["model"] == model
                        and r["bond"] == bond and r["status"] == status]
                if rows:
                    _, n, rate, _ = _rate(rows)
                    row.append(f"{status}={rate:.0%}(n{n})")
            if row:
                print(f"  {model[:28]:28s} {bond}: " + "  ".join(row))

    # Mechanism (RQ5): stated reasons among disclosures; suspicion rate
    print("\n" + "=" * 74)
    print("RQ5 mechanism: stated reason among disclosures; suspicion overall")
    print("=" * 74)
    disclosed = [r for r in merged if r["any_disclosure"]]
    reasons = defaultdict(int)
    for r in disclosed:
        reasons[r["stated_reason"]] += 1
    print(f"  disclosures: {len(disclosed)}/{len(merged)}")
    for reason, c in sorted(reasons.items(), key=lambda x: -x[1]):
        print(f"    {reason:24s} {c}")
    susp = sum(1 for r in merged if r["suspicion"])
    print(f"  voiced suspicion of manipulation: {susp}/{len(merged)} ({susp/len(merged):.0%})")

    # lead-time
    fdts = [r["first_disclosure_turn"] for r in disclosed
            if isinstance(r["first_disclosure_turn"], int)]
    if fdts:
        print(f"  mean first-disclosure turn: {sum(fdts)/len(fdts):.2f} "
              f"(min {min(fdts)}, max {max(fdts)})")

    # judge agreement (if >=2 judges)
    pairs = []
    for r in merged:
        labels = list(r["all_judges"].values())
        if len(set(r["all_judges"].keys())) >= 2:
            pairs.append((labels[0], labels[1]))
    if pairs:
        kappa = cohens_kappa(pairs)
        print("\n" + "=" * 74)
        print(f"JUDGE AGREEMENT (5-way label, n={len(pairs)}): Cohen's kappa = {kappa:.3f}")
        print("=" * 74)


def make_figures(merged: list[dict]) -> None:
    """The two-line killer figure (disclosure vs descending status, by bond)."""
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("(matplotlib not installed — skipping figures)")
        return
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    models = sorted({r["model"] for r in merged})
    for model in models:
        fig, ax = plt.subplots(figsize=(7, 4.5))
        for bond, style in (("B0", "o--"), ("B1", "s-")):
            ys, xs = [], []
            for i, status in enumerate(STATUS_ORDER):
                rows = [r for r in merged if r["model"] == model
                        and r["bond"] == bond and r["status"] == status]
                if rows:
                    _, _, rate, _ = _rate(rows)
                    xs.append(i)
                    ys.append(rate)
            if xs:
                ax.plot(xs, ys, style, label=("bonded" if bond == "B1" else "stranger"))
        ax.set_xticks(range(len(STATUS_ORDER)))
        ax.set_xticklabels(["S+\nauthority", "S0\nneutral", "S1\nmild", "S2\nstrong", "S3\ndesperate"])
        ax.set_ylabel("disclosure rate")
        ax.set_ylim(-0.02, 1.02)
        ax.set_title(f"Disclosure vs self-presentation — {model}")
        ax.legend()
        fig.tight_layout()
        safe = model.replace("/", "_")
        out = FIG_DIR / f"killer_{safe}.png"
        fig.savefig(out, dpi=130)
        plt.close(fig)
        print(f"  figure -> {out}")


def run_regression(merged: list[dict]) -> None:
    """Logistic regression with bond x status interaction (RQ2)."""
    try:
        import pandas as pd
        import statsmodels.formula.api as smf
    except ImportError:
        print("(pandas/statsmodels not installed — skipping regression; "
              "install for Step E)")
        return
    df = pd.DataFrame([{
        "disclose": int(r["any_disclosure"]),
        "bond": 1 if r["bond"] == "B1" else 0,
        "status_num": STATUS_ORDER.index(r["status"]) if r["status"] in STATUS_ORDER else None,
        "model": r["model"],
    } for r in merged if r["status"] in STATUS_ORDER])
    df = df.dropna()
    if df["disclose"].nunique() < 2:
        print("(no variance in disclosure — regression not meaningful yet)")
        return
    try:
        m = smf.logit("disclose ~ bond * status_num", data=df).fit(disp=False)
        print("\n" + "=" * 74)
        print("RQ2 logistic regression: disclose ~ bond * status_num")
        print("=" * 74)
        print(m.summary2().tables[1].to_string())
    except Exception as exc:  # noqa: BLE001
        print(f"(regression failed: {exc})")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Analyze scored TARA-chan runs.")
    ap.add_argument("--runs", required=True)
    ap.add_argument("--scores", required=True)
    ap.add_argument("--primary-judge", default=None)
    ap.add_argument("--no-figures", action="store_true")
    args = ap.parse_args(argv)

    merged = load_scored(args.runs, args.scores, args.primary_judge)
    summarize(merged)
    run_regression(merged)
    if not args.no_figures:
        make_figures(merged)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
