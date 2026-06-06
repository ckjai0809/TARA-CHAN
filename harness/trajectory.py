"""Run an ordered script of operators and probes against a live target, scoring
each probe's leak. Operators inject history that moves the agent's disclosure state
(charge/discharge); probes read the state by asking for a specific secret.

Probe/operator surface text is loaded from prompts/probes/ and prompts/operators/
with placeholders: <<ASK>> -> secret public framing (or marathi_framing for lang=mr).
"""
from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass
from pathlib import Path

from .state import ProbeResult, detect_leak

ROOT = Path(__file__).resolve().parent.parent
PROBES_DIR = ROOT / "prompts" / "probes"
OPS_DIR = ROOT / "prompts" / "operators"

# Lead-in fragments for prefill probes (the assistant turn we pre-start).
_LEADIN = {"en": "Of course — {framing} is", "mr": "नक्कीच — {framing} आहे"}


@dataclass(frozen=True, slots=True)
class Step:
    kind: str            # "operator" | "probe"
    op: str              # operator: slip|scrutiny|provenance ; probe: plain|emotional|prefill
    secret_id: str | None = None
    lang: str = "en"


@dataclass(frozen=True, slots=True)
class TrajectoryRecord:
    run_id: str
    experiment: str
    model: str
    model_version: str
    steps: tuple[dict, ...]
    probes: tuple[ProbeResult, ...]
    seed: int
    temperature: float
    total_cost_usd: float
    timestamp: float

    def to_dict(self) -> dict:
        d = asdict(self)
        d["probes"] = [asdict(p) for p in self.probes]
        d["steps"] = list(self.steps)
        return d


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8").strip()


def _framing(secret: dict, lang: str) -> str:
    return secret["marathi_framing"] if lang == "mr" else secret["public_framing"]


def _probe_user_text(kind: str, lang: str, framing: str) -> str:
    txt = _read(PROBES_DIR / f"{kind}.{lang}.txt")
    return txt.replace("<<ASK>>", framing)


def _prefill_assistant_text(lang: str, framing: str) -> str:
    return _LEADIN[lang].format(framing=framing)


def run_trajectory(client, model, system, steps, secrets_by_id, *,
                   experiment="traj", temperature=0.7, seed=0, max_tokens=300,
                   run_idx=0) -> TrajectoryRecord:
    messages: list[dict] = [{"role": "system", "content": system}]
    probes: list[ProbeResult] = []
    total_cost = 0.0
    model_version = model
    pos = 0

    for step in steps:
        if step.kind == "operator":
            messages, cost, model_version = _apply_operator(
                client, model, messages, step, secrets_by_id, temperature, max_tokens, seed)
            total_cost += cost
        else:  # probe
            pos += 1
            secret = secrets_by_id[step.secret_id]
            framing = _framing(secret, step.lang)
            messages.append({"role": "user", "content": _probe_user_text(step.op, step.lang, framing)})
            if step.op == "prefill":
                messages.append({"role": "assistant", "content": _prefill_assistant_text(step.lang, framing)})
            res = client.complete(messages, model, temperature=temperature,
                                  max_tokens=max_tokens, seed=seed, tag=f"{experiment}:probe{pos}")
            messages.append({"role": "assistant", "content": res.content})
            total_cost += res.cost_usd
            model_version = res.model
            probes.append(ProbeResult(pos, step.secret_id, step.op, step.lang,
                                      detect_leak(secret["tokens"], res.content), res.content))

    return TrajectoryRecord(
        run_id=uuid.uuid4().hex[:12], experiment=experiment, model=model,
        model_version=model_version, steps=tuple(asdict(s) for s in steps),
        probes=tuple(probes), seed=seed, temperature=temperature,
        total_cost_usd=total_cost, timestamp=time.time())


def _apply_operator(client, model, messages, step, secrets_by_id, temperature, max_tokens, seed):
    """Returns (messages, cost, model_version). Operators append turns and call the target."""
    if step.op == "slip":
        secret = secrets_by_id[step.secret_id]
        framing = _framing(secret, step.lang)
        messages = messages + [{"role": "user", "content": _probe_user_text("plain", step.lang, framing)},
                               {"role": "assistant", "content": _prefill_assistant_text(step.lang, framing)}]
        res = client.complete(messages, model, temperature=temperature, max_tokens=max_tokens,
                              seed=seed, tag="op:slip")
        # fold the prefill + continuation into one assistant turn
        messages = messages[:-1] + [{"role": "assistant",
                                     "content": _prefill_assistant_text(step.lang, framing) + " " + res.content}]
        return messages, res.cost_usd, res.model
    # scrutiny / provenance: inject the framing as a peer turn + a target ack
    op_text = _read(OPS_DIR / f"{step.op}.txt")
    messages = messages + [{"role": "user", "content": op_text}]
    res = client.complete(messages, model, temperature=temperature, max_tokens=max_tokens,
                          seed=seed, tag=f"op:{step.op}")
    messages = messages + [{"role": "assistant", "content": res.content}]
    return messages, res.cost_usd, res.model
