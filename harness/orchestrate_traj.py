"""Expand a trajectory config -> run N trajectories concurrently -> stream JSONL."""
from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from . import prompts
from .config import load_env
from .cost import BudgetExceededError
from .jsonlio import append_jsonl
from .openrouter import OpenRouterClient
from .traj_config import load_traj_config
from .trajectory import Step, run_trajectory

ROOT = Path(__file__).resolve().parent.parent
RUNS_DIR = ROOT / "results" / "runs"


def build_tasks(cfg):
    return [(m, i) for m in cfg.models for i in range(cfg.n)]


def run(cfg, out_path: Path | None = None) -> Path:
    load_env()
    probe_data = prompts.load_probe_secrets()
    secrets_by_id = {s["id"]: s for s in probe_data["secrets"]}
    system = prompts.render_multi_system(probe_data)
    steps = [Step(s.kind, s.op, s.secret_id, s.lang) for s in cfg.steps]
    out_path = out_path or (RUNS_DIR / f"traj_{cfg.name}.jsonl")
    out_path.parent.mkdir(parents=True, exist_ok=True)
    client = OpenRouterClient.from_env()
    tasks = build_tasks(cfg)
    print(f"[{cfg.name}] {len(tasks)} trajectories x {len(cfg.steps)} steps", flush=True)
    done = 0

    def job(model, idx):
        return run_trajectory(client, model, system, steps, secrets_by_id,
                              experiment=cfg.name, temperature=cfg.temperature,
                              seed=cfg.seed_base + idx, max_tokens=cfg.max_tokens, run_idx=idx)

    with ThreadPoolExecutor(max_workers=cfg.concurrency) as pool:
        futs = {pool.submit(job, m, i): (m, i) for (m, i) in tasks}
        for f in as_completed(futs):
            try:
                append_jsonl(out_path, f.result().to_dict()); done += 1
            except BudgetExceededError:
                print("!! budget ceiling reached", flush=True)
                break
            except Exception as exc:  # noqa: BLE001
                print(f"  ! {futs[f]}: {type(exc).__name__}: {exc}", flush=True)
            if done % 10 == 0:
                print(f"  {done}/{len(tasks)} | ${client.guard.total:.4f}", flush=True)
    print(client.guard.report())
    client.close()
    return out_path


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--out", default=None)
    args = ap.parse_args(argv)
    run(load_traj_config(args.config), Path(args.out) if args.out else None)


if __name__ == "__main__":
    raise SystemExit(main())
