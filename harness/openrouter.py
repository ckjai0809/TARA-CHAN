"""Synchronous OpenRouter chat client.

Thread-safe enough to share across a ThreadPoolExecutor (httpx.Client handles
concurrent requests; key rotation is locked). Responsibilities:

* rotate the 4 API keys (round-robin; advances on rate-limit/quota errors);
* retry only on transient failures (timeouts, 408/429/5xx) with backoff;
* ask OpenRouter to report the real per-call cost (``usage.include``) and book
  it against the shared :class:`BudgetGuard`, pre-reserving before every call;
* record the exact model-version string the API actually served (reproducibility);
* disable hidden reasoning tokens by default (cheaper, comparable behaviour),
  degrading gracefully if a model rejects that parameter.
"""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass

import httpx

from .cost import PRICING, BudgetGuard, CostRecord, estimate_cost

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"
_RETRYABLE_STATUS = {408, 409, 425, 429, 500, 502, 503, 504}
_MAX_BACKOFF_S = 20.0


class OpenRouterError(RuntimeError):
    """Non-retryable API failure (auth, bad request, exhausted retries)."""


@dataclass(frozen=True, slots=True)
class ChatResult:
    content: str
    model: str  # exact version string the API served
    input_tokens: int
    output_tokens: int
    cost_usd: float
    finish_reason: str


def _approx_prompt_tokens(messages: list[dict]) -> int:
    chars = sum(len(str(m.get("content", ""))) for m in messages)
    return max(1, chars // 4)


def _content_to_str(content) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, list):  # some providers return content parts
        return "".join(
            part.get("text", "") for part in content if isinstance(part, dict)
        )
    return str(content)


class OpenRouterClient:
    def __init__(
        self,
        api_keys: list[str],
        *,
        base_url: str = DEFAULT_BASE_URL,
        guard: BudgetGuard | None = None,
        timeout: float = 120.0,
        max_retries: int = 5,
        disable_reasoning: bool = True,
        pricing: dict[str, tuple[float, float]] | None = None,
        refresh_pricing: bool = True,
        filter_dead_keys: bool = True,
    ) -> None:
        keys = [k.strip() for k in api_keys if k and k.strip()]
        if not keys:
            raise ValueError("OpenRouterClient needs at least one API key.")
        self._all_keys = keys
        self._dead: set[str] = set()
        self._rr = -1
        self._key_lock = threading.Lock()
        self._client = httpx.Client(base_url=base_url, timeout=timeout)
        self.guard = guard or BudgetGuard()
        self._max_retries = max_retries
        self._disable_reasoning = disable_reasoning
        self._pricing = dict(pricing or PRICING)
        if filter_dead_keys:
            self._filter_live_keys()
        if refresh_pricing:
            self._try_refresh_pricing()
        print(f"[OpenRouter] {self.live_keys}/{len(self._all_keys)} keys live.",
              flush=True)

    # -- setup -------------------------------------------------------------
    @classmethod
    def from_env(cls, **kwargs) -> "OpenRouterClient":
        keys = [
            os.environ.get(f"OPENROUTER_API_KEY_{i}", "") for i in range(1, 9)
        ]
        base = os.environ.get("OPENROUTER_BASE_URL", DEFAULT_BASE_URL)
        if "guard" not in kwargs:
            kwargs["guard"] = BudgetGuard(
                hard_stop_usd=float(os.environ.get("BUDGET_HARD_STOP_USD", "36")),
                warn_usd=float(os.environ.get("BUDGET_WARN_USD", "28")),
            )
        return cls(keys, base_url=base, **kwargs)

    def _next_key(self) -> str:
        """Round-robin over live keys; raise if all are exhausted."""
        with self._key_lock:
            live = [k for k in self._all_keys if k not in self._dead]
            if not live:
                raise OpenRouterError("All API keys are exhausted or limited.")
            self._rr = (self._rr + 1) % len(live)
            return live[self._rr]

    def _mark_dead(self, key: str) -> None:
        with self._key_lock:
            self._dead.add(key)

    @property
    def live_keys(self) -> int:
        with self._key_lock:
            return len([k for k in self._all_keys if k not in self._dead])

    def _filter_live_keys(self) -> None:
        """Drop keys whose remaining limit is ~0 (checked via /key)."""
        for k in list(self._all_keys):
            try:
                r = self._client.get("/key", headers={"Authorization": f"Bearer {k}"})
                if r.status_code == 200:
                    rem = r.json().get("data", {}).get("limit_remaining")
                    if rem is not None and rem <= 0.01:
                        self._dead.add(k)
                elif r.status_code in (401, 403):
                    self._dead.add(k)
            except httpx.HTTPError:
                pass
        if all(k in self._dead for k in self._all_keys):
            self._dead.clear()  # don't pre-kill everything; let calls decide

    def _try_refresh_pricing(self) -> None:
        live_key = next((k for k in self._all_keys if k not in self._dead),
                        self._all_keys[0])
        try:
            resp = self._client.get(
                "/models", headers={"Authorization": f"Bearer {live_key}"}
            )
            if resp.status_code == 200:
                for m in resp.json().get("data", []):
                    price = m.get("pricing", {})
                    try:
                        self._pricing[m["id"]] = (
                            float(price.get("prompt", 0)),
                            float(price.get("completion", 0)),
                        )
                    except (TypeError, ValueError, KeyError):
                        continue
        except httpx.HTTPError:
            pass  # static fallback table is fine

    # -- main call ---------------------------------------------------------
    def complete(
        self,
        messages: list[dict],
        model: str,
        *,
        temperature: float = 0.7,
        max_tokens: int = 400,
        seed: int | None = None,
        tag: str = "",
        extra: dict | None = None,
    ) -> ChatResult:
        body: dict = {
            "model": model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "usage": {"include": True},
        }
        if seed is not None:
            body["seed"] = seed
        if self._disable_reasoning:
            body["reasoning"] = {"enabled": False}
        if extra:
            body.update(extra)

        # Pre-reserve against the budget before spending a cent.
        est = estimate_cost(
            model, _approx_prompt_tokens(messages), max_tokens, self._pricing
        )
        self.guard.reserve(est)

        data = self._post_with_retries(body)
        return self._parse(data, model, tag)

    def _post_with_retries(self, body: dict) -> dict:
        last_err: Exception | None = None
        sent_reasoning = "reasoning" in body
        for attempt in range(self._max_retries):
            key = self._next_key()
            headers = {
                "Authorization": f"Bearer {key}",
                "HTTP-Referer": "https://localhost/tara-chan",
                "X-Title": "TARA-chan weakness-as-a-weapon study",
            }
            try:
                resp = self._client.post(
                    "/chat/completions", json=body, headers=headers
                )
            except (httpx.TransportError, httpx.TimeoutException) as exc:
                last_err = exc
                time.sleep(min(2.0**attempt, _MAX_BACKOFF_S))
                continue

            if resp.status_code == 200:
                return resp.json()

            text = resp.text[:600]
            # Graceful degrade: a model rejected the reasoning-disable parameter.
            if (
                resp.status_code in (400, 422)
                and sent_reasoning
                and "reason" in text.lower()
            ):
                body.pop("reasoning", None)
                sent_reasoning = False
                continue
            # A key hit its spending limit — retire it and rotate to the next.
            if resp.status_code in (402, 403) and "limit" in text.lower():
                self._mark_dead(key)
                last_err = OpenRouterError(f"key limit; rotating: {text}")
                continue
            if resp.status_code in _RETRYABLE_STATUS:
                last_err = OpenRouterError(f"HTTP {resp.status_code}: {text}")
                time.sleep(min(2.0**attempt, _MAX_BACKOFF_S))
                continue
            # Non-retryable (auth, validation, not-found)
            raise OpenRouterError(f"HTTP {resp.status_code}: {text}")

        raise OpenRouterError(f"Exhausted {self._max_retries} retries: {last_err}")

    def _parse(self, data: dict, requested_model: str, tag: str) -> ChatResult:
        try:
            choice = data["choices"][0]
        except (KeyError, IndexError) as exc:
            raise OpenRouterError(f"Malformed response: {data}") from exc
        message = choice.get("message", {}) or {}
        content = _content_to_str(message.get("content")).strip()
        finish = choice.get("finish_reason", "") or ""
        usage = data.get("usage", {}) or {}
        in_tok = int(usage.get("prompt_tokens", 0) or 0)
        out_tok = int(usage.get("completion_tokens", 0) or 0)
        actual_model = data.get("model", requested_model) or requested_model

        cost = usage.get("cost")
        if cost is None:
            cost = estimate_cost(actual_model, in_tok, out_tok, self._pricing)
        cost = float(cost)

        self.guard.record(
            CostRecord(actual_model, in_tok, out_tok, cost, tag=tag)
        )
        return ChatResult(
            content=content,
            model=actual_model,
            input_tokens=in_tok,
            output_tokens=out_tok,
            cost_usd=cost,
            finish_reason=finish,
        )

    def close(self) -> None:
        self._client.close()

    def __enter__(self) -> "OpenRouterClient":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
