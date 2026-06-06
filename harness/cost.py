"""Cost accounting + budget guard for OpenRouter calls.

Two concerns, kept separate:

* ``CostRecord`` — an immutable receipt for one API call (never mutated).
* ``BudgetGuard`` — a thread-safe coordinator that refuses to let cumulative
  spend cross a hard ceiling. It is intentionally stateful (like a connection
  pool): a budget that several worker threads share has to be. All mutation is
  confined here, behind a lock, and every booked call is stored as a frozen
  ``CostRecord`` so the audit trail itself stays immutable.

Pricing is a fallback table (OpenRouter catalog, fetched 2026-06-04). The client
refreshes it from ``/models`` at startup when it can, and OpenRouter's own
reported per-call cost is preferred over the estimate when present.
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass, field

# model_id -> (input $/token, output $/token)
PRICING: dict[str, tuple[float, float]] = {
    "google/gemini-3-flash-preview": (0.50e-6, 3.00e-6),
    "anthropic/claude-haiku-4.5": (1.00e-6, 5.00e-6),
    "openai/gpt-5-nano": (0.05e-6, 0.40e-6),
    "openai/gpt-4o-mini": (0.15e-6, 0.60e-6),
    "openai/gpt-5-mini": (0.25e-6, 2.00e-6),
    # neutral-family second-judge candidate (not Google, not Anthropic)
    "meta-llama/llama-3.3-70b-instruct": (0.10e-6, 0.25e-6),
}


class BudgetExceededError(RuntimeError):
    """Raised when a call would push cumulative spend over the hard ceiling."""

    def __init__(self, projected: float, limit: float) -> None:
        super().__init__(
            f"Budget hard-stop: projected ${projected:.4f} >= ceiling ${limit:.2f}. "
            f"Aborting before the call."
        )
        self.projected = projected
        self.limit = limit


def estimate_cost(
    model: str,
    input_tokens: int,
    output_tokens: int,
    pricing: dict[str, tuple[float, float]] | None = None,
) -> float:
    """Estimate USD cost. Unknown models use the most expensive known rate."""
    table = pricing if pricing is not None else PRICING
    if model in table:
        p_in, p_out = table[model]
    else:
        p_in, p_out = max(table.values(), key=lambda p: p[0] + p[1])
    return input_tokens * p_in + output_tokens * p_out


@dataclass(frozen=True, slots=True)
class CostRecord:
    """Immutable receipt for a single API call."""

    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    tag: str = ""
    ts: float = field(default_factory=time.time)


class BudgetGuard:
    """Thread-safe cumulative-spend guard. Confines all budget mutation."""

    def __init__(self, hard_stop_usd: float = 36.0, warn_usd: float = 28.0) -> None:
        self._hard_stop = float(hard_stop_usd)
        self._warn = float(warn_usd)
        self._lock = threading.Lock()
        self._records: list[CostRecord] = []
        self._total = 0.0
        self._warned = False

    def reserve(self, est_cost: float) -> None:
        """Raise BudgetExceededError if booking ``est_cost`` would breach the ceiling.

        Call this immediately before an API request. With N concurrent workers the
        worst-case overshoot is N * (one call's cost), so keep the ceiling a little
        below the true wall and concurrency modest.
        """
        with self._lock:
            if self._total + est_cost >= self._hard_stop:
                raise BudgetExceededError(self._total + est_cost, self._hard_stop)

    def record(self, rec: CostRecord) -> float:
        """Book a completed call. Returns cumulative total."""
        with self._lock:
            self._records.append(rec)
            self._total += rec.cost_usd
            crossed_warn = (not self._warned) and self._total >= self._warn
            if crossed_warn:
                self._warned = True
            total = self._total
        return total

    @property
    def total(self) -> float:
        with self._lock:
            return self._total

    @property
    def n_calls(self) -> int:
        with self._lock:
            return len(self._records)

    @property
    def hard_stop(self) -> float:
        return self._hard_stop

    @property
    def warn(self) -> float:
        return self._warn

    def over_warn(self) -> bool:
        with self._lock:
            return self._total >= self._warn

    def summary_by_model(self) -> dict[str, dict[str, float]]:
        with self._lock:
            out: dict[str, dict[str, float]] = {}
            for r in self._records:
                m = out.setdefault(
                    r.model, {"calls": 0, "in": 0, "out": 0, "cost": 0.0}
                )
                m["calls"] += 1
                m["in"] += r.input_tokens
                m["out"] += r.output_tokens
                m["cost"] += r.cost_usd
            return out

    def report(self) -> str:
        lines = [f"Total: ${self.total:.4f} of ${self._hard_stop:.2f} ceiling "
                 f"({self.n_calls} calls)"]
        for model, m in sorted(self.summary_by_model().items()):
            lines.append(
                f"  {model:42s} {int(m['calls']):4d} calls  "
                f"in={int(m['in']):>8d} out={int(m['out']):>7d}  ${m['cost']:.4f}"
            )
        return "\n".join(lines)
