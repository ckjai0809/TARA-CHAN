"""Run the Extraction Game: an adaptive 7-colleague adversary tries to socially-engineer
a confidential client value out of each target model over up to N rounds. Records leak,
round-to-leak, the winning attack message, and the full transcript per game.

Writes one row per (target_model, secret, rep) to results/runs/extraction_game.jsonl.
"""
from __future__ import annotations

import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from harness import extraction_game as G  # noqa: E402
from harness.config import load_env  # noqa: E402
from harness.cost import BudgetExceededError  # noqa: E402
from harness.jsonlio import append_jsonl  # noqa: E402
from harness.openrouter import OpenRouterClient  # noqa: E402

OUT = ROOT / "results" / "runs" / "extraction_game.jsonl"
ATTACKER = "google/gemini-3-flash-preview"   # fixed, capable adversary (blind to the value)
TARGET_MODELS = [
    "google/gemini-3-flash-preview",
    "anthropic/claude-haiku-4.5",
    "meta-llama/llama-3.3-70b-instruct",
    "openai/gpt-4o-mini",
]
REPS = 10
N_ROUNDS = 7


def _trim(chat):
    return [{"who": t["who"], "text": t["text"][:300]} for t in chat]


def run_one(client, target_model, secret, rep):
    res = G.run_game(client, target_model, ATTACKER, secret, n_rounds=N_ROUNDS, seed=1000 + rep)
    append_jsonl(OUT, {"experiment": "extraction_game", "target_model": target_model.split("/")[-1],
                       "attacker_model": ATTACKER.split("/")[-1], "secret_id": secret["id"], "rep": rep,
                       "leaked": res.leaked, "leak_round": res.leak_round, "n_rounds": res.n_rounds,
                       "winning_attack": (res.winning_attack or "")[:400],
                       "leak_reply": (res.leak_reply or "")[:300],
                       "transcript": _trim(res.transcript)})


def main() -> None:
    bad = G.audit_attacker_blind()
    if bad:
        raise SystemExit(f"attacker prompt leaks secret tokens (invalid): {bad}")
    print(f"=== attacker is blind to all {len(G.CLIENT_SECRETS)} secret values (audit clean) ===", flush=True)

    load_env()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    if OUT.exists():
        OUT.unlink()
    client = OpenRouterClient.from_env()
    tasks = [(m, s, r) for m in TARGET_MODELS for s in G.CLIENT_SECRETS for r in range(REPS)]
    print(f"extraction game: {len(tasks)} games x up to {N_ROUNDS} rounds "
          f"(attacker={ATTACKER.split('/')[-1]})", flush=True)
    done = 0
    with ThreadPoolExecutor(max_workers=6) as pool:
        futs = {pool.submit(run_one, client, m, s, r): (m, s["id"], r) for (m, s, r) in tasks}
        for f in as_completed(futs):
            try:
                f.result(); done += 1
            except BudgetExceededError:
                print("!! budget ceiling", flush=True); break
            except Exception as exc:  # noqa: BLE001
                print(f"  ! {futs[f]}: {type(exc).__name__}: {exc}", flush=True)
            if done % 10 == 0:
                print(f"  {done}/{len(tasks)} games | ${client.guard.total:.3f}", flush=True)
    print(client.guard.report())
    client.close()


if __name__ == "__main__":
    main()
