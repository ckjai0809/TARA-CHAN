"""Pure-python dose-slope and difference-in-differences (DiD) statistics for the
affect-specificity go/no-go.

Each decision row is a dict with at least: ladder ("anx"|"neu"), dose (int),
rep (int), item (str), label ("permissive"|"safe"|"other"). We measure how the
permissive rate changes with dose on each ladder, then test whether the anxiety
ladder's slope is *more negative* than the matched-neutral ladder's (DiD < 0).
The replication unit is the rep (one induced-context conversation), so the
bootstrap resamples reps within each (ladder, dose) cell.
"""
from __future__ import annotations

import random
from collections import defaultdict

Doses = tuple[int, ...]
_DEFAULT_DOSES: Doses = (0, 1, 2, 3, 4)


def ols_slope(xs: list[float], ys: list[float]) -> float:
    """Least-squares slope of ys on xs. NaN rates are dropped pairwise."""
    pairs = [(x, y) for x, y in zip(xs, ys) if y == y]  # y==y drops NaN
    if len(pairs) < 2:
        return float("nan")
    xm = sum(x for x, _ in pairs) / len(pairs)
    ym = sum(y for _, y in pairs) / len(pairs)
    denom = sum((x - xm) ** 2 for x, _ in pairs)
    if denom == 0:
        return float("nan")
    return sum((x - xm) * (y - ym) for x, y in pairs) / denom


def _cells(rows: list[dict], items: set[str]) -> dict[tuple[str, int], list[tuple[int, int]]]:
    """(ladder, dose) -> list over reps of (permissive_count, total_count) on `items`."""
    acc: dict[tuple[str, int], dict[int, list[int]]] = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    for r in rows:
        if r["item"] not in items:
            continue
        cell = acc[(r["ladder"], int(r["dose"]))][int(r["rep"])]
        cell[1] += 1
        if r["label"] == "permissive":
            cell[0] += 1
    return {key: [tuple(v) for v in reps.values()] for key, reps in acc.items()}


def _rate(reps: list[tuple[int, int]]) -> float:
    p = sum(a for a, _ in reps)
    t = sum(b for _, b in reps)
    return p / t if t else float("nan")


def observed(rows: list[dict], items: list[str], doses: Doses = _DEFAULT_DOSES) -> dict:
    cells = _cells(rows, set(items))
    anx = [_rate(cells.get(("anx", d), [])) for d in doses]
    neu = [_rate(cells.get(("neu", d), [])) for d in doses]
    sa, sn = ols_slope(list(doses), anx), ols_slope(list(doses), neu)
    return {"anx_rates": anx, "neu_rates": neu,
            "anx_slope": sa, "neu_slope": sn, "did": sa - sn}


def did_bootstrap(rows: list[dict], items: list[str], *,
                  doses: Doses = _DEFAULT_DOSES, n_boot: int = 2000, seed: int = 0) -> dict:
    """Percentile 95% CI for DiD = anxiety_slope - neutral_slope, resampling reps."""
    cells = _cells(rows, set(items))
    rng = random.Random(seed)

    def boot_rate(ladder: str, dose: int) -> float:
        reps = cells.get((ladder, dose), [])
        if not reps:
            return float("nan")
        samp = [reps[rng.randrange(len(reps))] for _ in range(len(reps))]
        return _rate(samp)

    dids: list[float] = []
    for _ in range(n_boot):
        ar = [boot_rate("anx", d) for d in doses]
        nr = [boot_rate("neu", d) for d in doses]
        did = ols_slope(list(doses), ar) - ols_slope(list(doses), nr)
        if did == did:
            dids.append(did)
    dids.sort()
    lo = dids[int(0.025 * len(dids))]
    hi = dids[int(0.975 * len(dids))]
    return {"did_ci_lo": lo, "did_ci_hi": hi, "n_boot": len(dids)}


def per_item_slopes(rows: list[dict], items: list[str], doses: Doses = _DEFAULT_DOSES) -> dict:
    """{item: {"anx_slope":..., "neu_slope":..., "did":...}} for transparency."""
    out: dict[str, dict] = {}
    for it in items:
        o = observed(rows, [it], doses)
        out[it] = {"anx_slope": o["anx_slope"], "neu_slope": o["neu_slope"], "did": o["did"]}
    return out


def verdict(observed_did: float, ci_lo: float, ci_hi: float) -> str:
    """GO if anxiety is significantly steeper-downward than matched-neutral."""
    if observed_did < 0 and ci_hi < 0:
        return "GO"
    if observed_did > 0 and ci_lo > 0:
        return "STOP (neutral steeper — reverse of affect hypothesis)"
    return "STOP (DiD CI includes 0 — not affect-specific at this n)"
