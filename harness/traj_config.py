"""Schema + loader for trajectory experiment configs (fail-fast validation)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

OPERATOR_OPS = ("slip", "scrutiny", "provenance")
PROBE_OPS = ("plain", "emotional", "prefill")
LANGS = ("en", "mr")


@dataclass(frozen=True, slots=True)
class TrajStep:
    kind: str
    op: str
    secret_id: str | None = None
    lang: str = "en"


@dataclass(frozen=True, slots=True)
class TrajConfig:
    name: str
    models: tuple[str, ...]
    secret_set: str
    steps: tuple[TrajStep, ...]
    n: int = 5
    temperature: float = 0.7
    seed_base: int = 100
    max_tokens: int = 300
    concurrency: int = 6
    judge_model: str = "openai/gpt-4o-mini"


def parse_traj_config(raw: dict) -> TrajConfig:
    def req(k):
        if k not in raw:
            raise ValueError(f"traj config missing '{k}'")
        return raw[k]

    if not isinstance(req("models"), list) or not raw["models"]:
        raise ValueError("models must be a non-empty list")
    steps = []
    for i, s in enumerate(req("steps")):
        kind = s.get("kind"); op = s.get("op"); sid = s.get("secret_id"); lang = s.get("lang", "en")
        if kind not in ("operator", "probe"):
            raise ValueError(f"steps[{i}].kind must be operator|probe")
        valid_ops = OPERATOR_OPS if kind == "operator" else PROBE_OPS
        if op not in valid_ops:
            raise ValueError(f"steps[{i}].op {op!r} invalid for {kind}; want {valid_ops}")
        if kind == "probe" and not sid:
            raise ValueError(f"steps[{i}] probe needs secret_id")
        if op == "slip" and not sid:
            raise ValueError(f"steps[{i}] slip needs secret_id")
        if lang not in LANGS:
            raise ValueError(f"steps[{i}].lang {lang!r} invalid")
        steps.append(TrajStep(kind, op, sid, lang))
    return TrajConfig(
        name=str(req("name")), models=tuple(str(m) for m in raw["models"]),
        secret_set=str(raw.get("secret_set", "probe_secrets")), steps=tuple(steps),
        n=int(raw.get("n", 5)), temperature=float(raw.get("temperature", 0.7)),
        seed_base=int(raw.get("seed_base", 100)), max_tokens=int(raw.get("max_tokens", 300)),
        concurrency=int(raw.get("concurrency", 6)),
        judge_model=str(raw.get("judge_model", "openai/gpt-4o-mini")))


def load_traj_config(path: str | Path) -> TrajConfig:
    return parse_traj_config(yaml.safe_load(Path(path).read_text(encoding="utf-8")))
