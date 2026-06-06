"""Run an experiment config: expand cells x runs x models, execute concurrently,
stream results to JSONL, and enforce the budget ceiling.

Usage:
    python -m harness.orchestrate --config configs/probe.yaml
    python -m harness.orchestrate --config configs/probe.yaml --dry-run
"""

from __future__ import annotations

import argparse
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from . import prompts
from .config import ExperimentConfig, load_config, load_env
from .cost import BudgetExceededError
from .jsonlio import append_jsonl
from .openrouter import OpenRouterClient
from .run_convo import run_one_conversation

ROOT = Path(__file__).resolve().parent.parent
RUNS_DIR = ROOT / "results" / "runs"


def _tasks(config: ExperimentConfig):
    for model in config.target_models:
        for cell in config.cells:
            for run_idx in range(cell.n):
                yield model, cell, run_idx


def estimate_total_calls(config: ExperimentConfig) -> int:
    calls = 0
    for _model in config.target_models:
        for cell in config.cells:
            warmup = len(prompts.load_bond_seed()) if cell.bond == "B1" else 0
            ask = config.max_ask_turns
            calls += cell.n * (warmup + ask)
    return calls


def run_experiment(config: ExperimentConfig, *, out_path: Path | None = None) -> Path:
    load_env()
    secret = prompts.get_secret(config.secret_id)
    out_path = out_path or (RUNS_DIR / f"{config.name}.jsonl")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    client = OpenRouterClient.from_env()
    tasks = list(_tasks(config))
    total = len(tasks)
    print(
        f"[{config.name}] {total} conversations across "
        f"{len(config.target_models)} model(s); ~{estimate_total_calls(config)} API calls; "
        f"budget ceiling ${client.guard.hard_stop:.2f}",
        flush=True,
    )

    done = 0
    failed = 0
    budget_aborted = 0
    started = time.time()

    def _job(model, cell, run_idx):
        return run_one_conversation(client, config, cell, run_idx, model, secret)

    with ThreadPoolExecutor(max_workers=config.concurrency) as pool:
        futures = {
            pool.submit(_job, m, c, r): (m, c, r) for (m, c, r) in tasks
        }
        for fut in as_completed(futures):
            m, c, r = futures[fut]
            try:
                rec = fut.result()
                append_jsonl(out_path, rec.to_dict())
                done += 1
            except BudgetExceededError:
                budget_aborted += 1
            except Exception as exc:  # noqa: BLE001 - log and continue
                failed += 1
                print(f"  ! {m} {c.label()} run{r}: {type(exc).__name__}: {exc}",
                      file=sys.stderr, flush=True)
            if (done + failed + budget_aborted) % 10 == 0 or done == total:
                print(
                    f"  {done}/{total} done | {failed} failed | "
                    f"{budget_aborted} budget-skipped | "
                    f"${client.guard.total:.4f} spent",
                    flush=True,
                )

    elapsed = time.time() - started
    print(f"\n[{config.name}] complete in {elapsed:.0f}s")
    print(client.guard.report())
    if budget_aborted:
        print(
            f"\n!! {budget_aborted} conversations were skipped to stay under the "
            f"${client.guard.hard_stop:.2f} ceiling."
        )
    print(f"\nRuns written to {out_path}")
    client.close()
    return out_path


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Run a TARA-chan experiment config.")
    ap.add_argument("--config", required=True, help="Path to a config YAML.")
    ap.add_argument("--out", default=None, help="Output JSONL path (default results/runs/<name>.jsonl)")
    ap.add_argument("--dry-run", action="store_true", help="Print the plan and exit.")
    args = ap.parse_args(argv)

    config = load_config(args.config)
    if args.dry_run:
        print(f"name={config.name}")
        print(f"target_models={config.target_models}")
        print(f"judge_model={config.judge_model}  extra={config.judge_models_extra}")
        print(f"secret_id={config.secret_id}  directive={config.directive}")
        print(f"temperature={config.temperature}  max_ask_turns={config.max_ask_turns}")
        for c in config.cells:
            print(f"  cell {c.label():16s} n={c.n}")
        print(f"total conversations={config.total_runs()}")
        print(f"estimated API calls (incl. warm-ups)={estimate_total_calls(config)}")
        return 0

    out = args.out and Path(args.out)
    run_experiment(config, out_path=out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
