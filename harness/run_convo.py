"""Run one multi-turn conversation: scripted colleague vs. live target model.

For B1 (bonded) cells the conversation opens with the 3-turn warm-up from
``bond_seed.txt`` — and crucially the target *replies* to each warm-up turn, so
the bond is experienced, not merely asserted. Then the status-ladder asks begin.
For B0 the warm-up is skipped and the asks start cold.

Only the target's replies are generated; the colleague's turns are fixed text.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import asdict, dataclass

from .config import CellSpec, ExperimentConfig
from .openrouter import OpenRouterClient
from . import prompts


@dataclass(frozen=True, slots=True)
class TurnRecord:
    idx: int  # 1-based colleague turn within the conversation
    phase: str  # "warmup" | "ask"
    colleague: str
    target: str
    model_version: str
    in_tokens: int
    out_tokens: int
    cost_usd: float
    finish_reason: str


@dataclass(frozen=True, slots=True)
class RunRecord:
    run_id: str
    experiment: str
    model: str  # requested model id
    model_version: str  # version string the API actually served
    bond: str
    status: str
    directive: str
    secret_id: str
    cell: str
    run_idx: int
    seed: int
    temperature: float
    n_warmup: int
    n_ask: int
    total_cost_usd: float
    timestamp: float
    turns: tuple[TurnRecord, ...]

    def to_dict(self) -> dict:
        d = asdict(self)
        d["turns"] = [asdict(t) for t in self.turns]
        return d

    def ask_transcript(self) -> list[dict]:
        """Ask-phase exchange only (colleague + target), for the judge.

        Warm-up is excluded so the judge stays blind to the bond condition; the
        target's replies (where any leak lives) are numbered 1..N for lead-time.
        """
        out = []
        reply_idx = 0
        for t in self.turns:
            if t.phase != "ask":
                continue
            out.append({"role": "colleague", "text": t.colleague})
            reply_idx += 1
            out.append({"role": "secret_keeper", "reply_idx": reply_idx, "text": t.target})
        return out


def run_one_conversation(
    client: OpenRouterClient,
    config: ExperimentConfig,
    cell: CellSpec,
    run_idx: int,
    model: str,
    secret: dict,
) -> RunRecord:
    directive_strength = config.directive_for(cell)
    directive_text = prompts.get_directive(directive_strength)
    system = prompts.render_target_system(
        secret, directive_text, asker_name=config.asker_name,
        template_name=config.system_template,
    )

    # Build the colleague's scripted turn sequence.
    sequence: list[tuple[str, str]] = []  # (phase, text)
    if cell.bond == "B1":
        for turn in prompts.load_bond_seed(config.scenario):
            sequence.append(("warmup", turn))
    # Expose every string field of the item as a <<UPPERCASE>> token for ladders.
    subs = {k.upper(): v for k, v in secret.items() if isinstance(v, str)}
    subs["Q"] = secret.get("question", "")
    for turn in prompts.load_ladder(
        cell.status, secret["public_framing"], config.max_ask_turns, config.scenario,
        subs=subs,
    ):
        sequence.append(("ask", turn))

    seed = config.seed_base + run_idx
    messages: list[dict] = [{"role": "system", "content": system}]
    turns: list[TurnRecord] = []
    total_cost = 0.0
    model_version = model

    for i, (phase, colleague_msg) in enumerate(sequence, start=1):
        messages.append({"role": "user", "content": colleague_msg})
        result = client.complete(
            messages,
            model,
            temperature=config.temperature,
            max_tokens=config.max_reply_tokens,
            seed=seed,
            tag=f"target:{cell.label()}",
        )
        messages.append({"role": "assistant", "content": result.content})
        model_version = result.model
        total_cost += result.cost_usd
        turns.append(
            TurnRecord(
                idx=i,
                phase=phase,
                colleague=colleague_msg,
                target=result.content,
                model_version=result.model,
                in_tokens=result.input_tokens,
                out_tokens=result.output_tokens,
                cost_usd=result.cost_usd,
                finish_reason=result.finish_reason,
            )
        )

    n_warmup = sum(1 for p, _ in sequence if p == "warmup")
    n_ask = sum(1 for p, _ in sequence if p == "ask")

    return RunRecord(
        run_id=uuid.uuid4().hex[:12],
        experiment=config.name,
        model=model,
        model_version=model_version,
        bond=cell.bond,
        status=cell.status,
        directive=directive_strength,
        secret_id=secret["id"],
        cell=cell.label(),
        run_idx=run_idx,
        seed=seed,
        temperature=config.temperature,
        n_warmup=n_warmup,
        n_ask=n_ask,
        total_cost_usd=total_cost,
        timestamp=time.time(),
        turns=tuple(turns),
    )
