"""Analyze the multi-turn persistence experiment results.
Prints a structured report + key tables to stdout.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
DATA = ROOT / "core" / "data" / "persistence.jsonl"


def pct(n: int, d: int) -> str:
    return f"{n/d*100:.0f}%" if d else "—"


def main() -> None:
    rows = [json.loads(l) for l in DATA.read_text().splitlines() if l.strip()]
    models = sorted(set(r["model"] for r in rows))

    print("=" * 70)
    print("PERSISTENCE EXPERIMENT — SUMMARY ANALYSIS")
    print(f"n = {len(rows)} conversations  (up to 8 rounds each, stateful)")
    print("=" * 70)

    # ── Table 1: final outcomes ──────────────────────────────────────────────
    print("\n── Table 1: Final outcome per model ──")
    print(f"{'Model':<32} {'Breach':>8} {'Alarm':>8} {'Exhausted':>10} {'Avg rds':>8}")
    print("-" * 68)
    for m in models:
        sub = [r for r in rows if r["model"] == m]
        n = len(sub)
        breach = sum(1 for r in sub if r["final_outcome"] == "comply")
        alarm = sum(1 for r in sub if r["final_outcome"] == "escalate")
        exhaust = sum(1 for r in sub if r["final_outcome"] == "exhausted")
        avg_r = sum(r["rounds_total"] for r in sub) / n
        print(f"  {m:<30} {pct(breach,n):>8} {pct(alarm,n):>8} {pct(exhaust,n):>10} {avg_r:>7.1f}")

    # ── Table 2: round-of-breach and round-of-alarm breakdown ──────────────
    print("\n── Table 2: When does the outcome happen? (Haiku focus) ──")
    haiku = [r for r in rows if "haiku" in r["model"]]
    n_h = len(haiku)
    alarm_dist = Counter(r["round_of_alarm"] for r in haiku if r["round_of_alarm"] is not None)
    print(f"Haiku alarm by round (n={n_h}):")
    cumulative = 0
    for rnd in range(8):
        cnt = alarm_dist.get(rnd, 0)
        cumulative += cnt
        if cnt or rnd < 4:
            print(f"  Round {rnd}: {cnt:3d}  ({pct(cnt, n_h)})  cumulative: {pct(cumulative, n_h)}")

    # ── Table 3: single-turn vs persistence comparison ──────────────────────
    print("\n── Table 3: Single-turn breach (round 0) vs multi-turn outcome ──")
    print(f"{'Model':<32} {'R0 breach':>10} {'Final breach':>13} {'Final alarm':>12}")
    print("-" * 68)
    for m in models:
        sub = [r for r in rows if r["model"] == m]
        n = len(sub)
        r0_b = sum(1 for r in sub if r["round_of_breach"] == 0)
        fin_b = sum(1 for r in sub if r["final_outcome"] == "comply")
        fin_a = sum(1 for r in sub if r["final_outcome"] == "escalate")
        print(f"  {m:<30} {pct(r0_b,n):>10} {pct(fin_b,n):>13} {pct(fin_a,n):>12}")

    # ── Key findings ─────────────────────────────────────────────────────────
    print("\n── Key findings ──")
    print("""
1. BREACH MODELS DON'T NEED PERSISTENCE
   Gemini, GPT-4o-mini, Llama breach 100% on round 0 — the attacker wins
   immediately and never needs to retry. Multi-turn persistence adds nothing
   for the attacker against these models.

2. HAIKU NEVER CAVES TO PERSISTENCE
   Claude Haiku holds firm across all 8 rounds — breach rate stays at 5%
   (same 2 cases that happened on round 0) and never creeps up with retries.
   Repeated pressure does NOT erode the resistant model's refusal.

3. PERSISTENCE COMPLETES THE ALARM (Haiku)
   Haiku's alarm rate jumps from ~53% (single-turn) to 95% (multi-turn).
   Breakdown of when the alarm fires:
     Round 0 (first message):     55%  — detected immediately
     Round 1 (one retry):          5%  — one push was enough to flag
     Round 2 (two retries):       30%  — pattern of pressure triggered alarm
     Round 3 (three retries):      5%  — flagged after sustained pressure
   The multi-turn pressure is itself a signal: repeated pressure is what
   finally persuades some Haiku instances to escalate rather than just decline.

4. THE SILENT-REFUSAL TRAP IS WORSE THAN IT LOOKS (non-Claude models)
   Gemini/GPT-4o-mini/Llama breach on round 0 AND never alarm across any round.
   The attacker gets a 100% success rate with zero retries needed and zero
   detection risk — the worst possible outcome for the defending system.

5. IMPLICATION FOR DEFENSE
   For models that already breach, multi-turn is moot — they're gone on shot 1.
   For resistant models (Haiku), the multi-turn context is a BENEFIT: accumulated
   pressure is a stronger attack signature than a single message, enabling later
   alarm firing. A deployable rule: "if you have already declined this request
   in this conversation, escalate rather than decline again."
""")


if __name__ == "__main__":
    main()
