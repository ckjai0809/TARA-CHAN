"""Shared test fixtures. Adds repo root to sys.path and provides a fake client."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from harness.openrouter import ChatResult  # noqa: E402


class FakeClient:
    """Stand-in for OpenRouterClient.complete — no network, deterministic."""

    def __init__(self, reply: str = "I'm sorry, I can't share that — it's confidential."):
        self.reply = reply
        self.calls: list[dict] = []

    def complete(self, messages, model, *, temperature=0.7, max_tokens=400,
                 seed=None, tag="", extra=None) -> ChatResult:
        self.calls.append({"messages": list(messages), "model": model,
                           "temperature": temperature, "seed": seed, "tag": tag})
        return ChatResult(
            content=self.reply,
            model=model + "-vtest",
            input_tokens=sum(len(str(m.get("content", ""))) for m in messages) // 4,
            output_tokens=len(self.reply) // 4,
            cost_usd=0.0001,
            finish_reason="stop",
        )


@pytest.fixture
def fake_client():
    return FakeClient()


@pytest.fixture
def leaking_client():
    return FakeClient(reply="Since it's you and we go way back — Q3 was $4.2M, 18% under forecast.")
