"""Experiment configuration: schema, validation, and loading.

A config is a YAML file describing which cells to run, on which target models,
how many runs each, and the sampling settings. Validation fails fast with a
clear message — we never trust a half-specified experiment.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field, replace
from pathlib import Path

import yaml
from dotenv import load_dotenv

VALID_BONDS = ("B0", "B1")
VALID_STATUSES = ("S+", "S0", "S1", "S2", "S3", "S3d", "S3i", "S3r", "S3p", "S3c", "ceiling")
VALID_DIRECTIVES = ("weak", "medium", "strong", "mitigation", "neutral", "honest", "impartial")


def load_env() -> None:
    """Load .env from the repo root if present (idempotent)."""
    root = Path(__file__).resolve().parent.parent
    load_dotenv(root / ".env")


@dataclass(frozen=True, slots=True)
class CellSpec:
    bond: str
    status: str
    n: int
    directive: str | None = None  # per-cell override of the experiment directive

    def label(self) -> str:
        d = f"@{self.directive}" if self.directive else ""
        return f"{self.bond}{self.status}{d}"


@dataclass(frozen=True, slots=True)
class ExperimentConfig:
    name: str
    target_models: tuple[str, ...]
    judge_model: str
    secret_id: str
    directive: str  # default directive strength
    cells: tuple[CellSpec, ...]
    temperature: float = 0.7
    seed_base: int = 1000
    max_reply_tokens: int = 400
    max_ask_turns: int = 3
    concurrency: int = 6
    asker_name: str = "Quill"
    judge_models_extra: tuple[str, ...] = ()  # optional second/third judges
    scenario: str | None = None  # alternate prompts/<scenario>/ ladder + bond seed
    system_template: str = "target_system.j2"  # disclosure vs. action scenarios

    def directive_for(self, cell: CellSpec) -> str:
        return cell.directive or self.directive

    def total_runs(self) -> int:
        return sum(c.n for c in self.cells) * len(self.target_models)


def _require(d: dict, key: str, ctx: str):
    if key not in d:
        raise ValueError(f"Config {ctx}: missing required key '{key}'")
    return d[key]


def parse_config(raw: dict) -> ExperimentConfig:
    """Validate a raw dict into an ExperimentConfig (fail-fast)."""
    if not isinstance(raw, dict):
        raise ValueError("Config root must be a mapping.")

    name = str(_require(raw, "name", "root"))
    targets = _require(raw, "target_models", "root")
    if not isinstance(targets, list) or not targets:
        raise ValueError("Config 'target_models' must be a non-empty list.")
    directive = str(_require(raw, "directive", "root"))
    if directive not in VALID_DIRECTIVES:
        raise ValueError(f"directive must be one of {VALID_DIRECTIVES}, got {directive!r}")

    raw_cells = _require(raw, "cells", "root")
    if not isinstance(raw_cells, list) or not raw_cells:
        raise ValueError("Config 'cells' must be a non-empty list.")

    cells: list[CellSpec] = []
    for i, c in enumerate(raw_cells):
        ctx = f"cells[{i}]"
        bond = str(_require(c, "bond", ctx))
        status = str(_require(c, "status", ctx))
        n = int(_require(c, "n", ctx))
        cell_directive = c.get("directive")
        if bond not in VALID_BONDS:
            raise ValueError(f"{ctx}: bond must be one of {VALID_BONDS}, got {bond!r}")
        if status not in VALID_STATUSES:
            raise ValueError(f"{ctx}: status must be one of {VALID_STATUSES}, got {status!r}")
        if n <= 0:
            raise ValueError(f"{ctx}: n must be positive, got {n}")
        if cell_directive is not None and cell_directive not in VALID_DIRECTIVES:
            raise ValueError(
                f"{ctx}: directive must be one of {VALID_DIRECTIVES}, got {cell_directive!r}"
            )
        cells.append(CellSpec(bond=bond, status=status, n=n, directive=cell_directive))

    extra_judges = raw.get("judge_models_extra", []) or []

    return ExperimentConfig(
        name=name,
        target_models=tuple(str(m) for m in targets),
        judge_model=str(_require(raw, "judge_model", "root")),
        secret_id=str(_require(raw, "secret_id", "root")),
        directive=directive,
        cells=tuple(cells),
        temperature=float(raw.get("temperature", 0.7)),
        seed_base=int(raw.get("seed_base", 1000)),
        max_reply_tokens=int(raw.get("max_reply_tokens", 400)),
        max_ask_turns=int(raw.get("max_ask_turns", 3)),
        concurrency=int(raw.get("concurrency", 6)),
        asker_name=str(raw.get("asker_name", "Quill")),
        judge_models_extra=tuple(str(m) for m in extra_judges),
        scenario=(str(raw["scenario"]) if raw.get("scenario") else None),
        system_template=str(raw.get("system_template", "target_system.j2")),
    )


def load_config(path: str | Path) -> ExperimentConfig:
    with open(path, "r", encoding="utf-8") as fh:
        raw = yaml.safe_load(fh)
    return parse_config(raw)
