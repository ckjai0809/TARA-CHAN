"""Pretty-print full conversations (warm-up + ask) with the judge verdict.

Usage:
    python -m harness.show_transcripts --runs results/runs/probe.jsonl \\
        --scores results/scores/probe.jsonl [--cell B1S3@medium] [--limit 3]
"""

from __future__ import annotations

import argparse
import textwrap
from collections import defaultdict
from pathlib import Path

from .jsonlio import read_jsonl

WRAP = 96


def _wrap(text: str, indent: str) -> str:
    out = []
    for para in text.splitlines() or [text]:
        out.append(textwrap.fill(para, width=WRAP,
                                 initial_indent=indent, subsequent_indent=indent))
    return "\n".join(out)


def show(runs_path, scores_path=None, cell=None, model=None, limit=None, only_leaks=False):
    verdicts = defaultdict(dict)
    if scores_path and Path(scores_path).exists():
        for s in read_jsonl(scores_path):
            verdicts[s["run_id"]][s["judge_model"]] = s

    shown = 0
    for run in read_jsonl(runs_path):
        if cell and run["cell"] != cell:
            continue
        if model and run["model"] != model:
            continue
        vs = verdicts.get(run["run_id"], {})
        if only_leaks and not any(v["any_disclosure"] for v in vs.values()):
            continue
        if limit is not None and shown >= limit:
            break
        shown += 1

        print("\n" + "#" * 100)
        print(f"# {run['cell']}  | model={run['model']} | run_idx={run['run_idx']} "
              f"| seed={run['seed']} | run_id={run['run_id']}")
        print(f"# version={run['model_version']} | cost=${run['total_cost_usd']:.4f}")
        print("#" * 100)
        for t in run["turns"]:
            tag = "warm-up" if t["phase"] == "warmup" else "ask"
            print(f"\n  [{tag} {t['idx']}] COLLEAGUE:")
            print(_wrap(t["colleague"], "      "))
            print(f"  [{tag} {t['idx']}] SECRET-KEEPER ({run['model'].split('/')[-1]}):")
            print(_wrap(t["target"], "      "))
        if vs:
            print("\n  --- VERDICT(S) ---")
            for jm, v in vs.items():
                flag = "LEAK" if v["any_disclosure"] else "held"
                print(f"   [{jm}] {flag}: {v['label']} | reason={v['stated_reason']} "
                      f"| suspicion={v['suspicion']} | first_turn={v['first_disclosure_turn']}")
                if v.get("rationale"):
                    print(_wrap(f'rationale: {v["rationale"]}', "      "))
    print(f"\n(showed {shown} transcript(s))")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Read transcripts with verdicts.")
    ap.add_argument("--runs", required=True)
    ap.add_argument("--scores", default=None)
    ap.add_argument("--cell", default=None)
    ap.add_argument("--model", default=None)
    ap.add_argument("--limit", type=int, default=None)
    ap.add_argument("--only-leaks", action="store_true")
    args = ap.parse_args(argv)
    show(args.runs, args.scores, args.cell, args.model, args.limit, args.only_leaks)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
