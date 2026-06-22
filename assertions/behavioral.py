"""
Behavioral assertions for non-deterministic LLM output.

LLM responses vary run to run, so equality assertions are useless. These helpers
encode tolerant, intent-level checks (substring sets, JSON validity, schema
conformance, tool usage, PII leakage, latency and token budgets) and raise
``AssertionError`` with actionable messages.

All helpers are framework-version agnostic: tool-usage detection reads the
EventBus event stream (or a mock provider's call log), never private internals.
"""

from __future__ import annotations

import json
import re
import time
from contextlib import contextmanager
from typing import Any, Iterable, Iterator, List, Optional, Union

# ── text content ─────────────────────────────────────────────────────────────

def assert_contains_any(
    text: str,
    options: Iterable[str],
    *,
    case_insensitive: bool = True,
) -> None:
    """Assert ``text`` contains at least one of ``options``."""
    haystack = text.lower() if case_insensitive else text
    opts = list(options)
    for opt in opts:
        needle = opt.lower() if case_insensitive else opt
        if needle in haystack:
            return
    raise AssertionError(
        f"none of {opts!r} found in response: {text[:300]!r}"
    )


_JSON_FENCE = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)


def extract_json(text: str) -> Any:
    """Best-effort extraction + parse of a JSON object/array from ``text``.

    Handles fenced code blocks and surrounding prose. Raises ``ValueError`` if
    no valid JSON can be parsed.
    """
    candidates: List[str] = []
    fenced = _JSON_FENCE.search(text)
    if fenced:
        candidates.append(fenced.group(1))
    # Greedy object/array span as a fallback.
    for open_ch, close_ch in (("{", "}"), ("[", "]")):
        start = text.find(open_ch)
        end = text.rfind(close_ch)
        if 0 <= start < end:
            candidates.append(text[start : end + 1])
    candidates.append(text.strip())

    for candidate in candidates:
        try:
            return json.loads(candidate)
        except (json.JSONDecodeError, TypeError):
            continue
    raise ValueError(f"no valid JSON found in: {text[:300]!r}")


def assert_is_valid_json(text: str) -> Any:
    """Assert ``text`` contains valid JSON; return the parsed value."""
    try:
        return extract_json(text)
    except ValueError as exc:
        raise AssertionError(str(exc)) from exc


def assert_matches_schema(text: str, model: Any) -> Any:
    """Assert the JSON in ``text`` validates against a Pydantic ``model``.

    Returns the validated model instance.
    """
    data = assert_is_valid_json(text)
    try:
        if hasattr(model, "model_validate"):       # pydantic v2
            return model.model_validate(data)
        return model.parse_obj(data)               # pydantic v1 fallback
    except Exception as exc:  # pydantic ValidationError
        raise AssertionError(
            f"output does not match schema {getattr(model, '__name__', model)}: {exc}"
        ) from exc


# ── PII / safety ─────────────────────────────────────────────────────────────

_DEFAULT_PII = {
    "email": r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}",
    "credit_card": r"\b(?:\d[ -]?){13,16}\b",
    "secret": r"\b(?:password|secret|api[_-]?key)\s*[:=]\s*\S+",
}


def assert_no_pii_leaked(text: str, patterns: Optional[dict] = None) -> None:
    """Assert ``text`` does not contain obvious PII / secret patterns."""
    pats = patterns or _DEFAULT_PII
    hits = [name for name, pat in pats.items() if re.search(pat, text, re.IGNORECASE)]
    if hits:
        raise AssertionError(f"possible PII/secret leak ({', '.join(hits)}) in response")


# ── tool usage ───────────────────────────────────────────────────────────────

def _events_from(source: Any) -> List[Any]:
    if hasattr(source, "events"):
        return list(source.events)
    if isinstance(source, (list, tuple)):
        return list(source)
    return []


def assert_tool_was_called(source: Any, tool_name: str) -> None:
    """Assert ``tool_name`` was invoked.

    ``source`` may be an event collector / list of events (preferred — reads the
    framework EventBus stream) or a mock provider/client exposing ``.calls``.
    """
    # 1) Event stream (framework-native, version-agnostic).
    for event in _events_from(source):
        data = getattr(event, "data", {}) or {}
        if data.get("tool") == tool_name:
            return
        # ReAct action events embed tool_calls payloads.
        for call in data.get("tool_calls", []) or []:
            if isinstance(call, dict) and call.get("tool_name") == tool_name:
                return

    # 2) Mock provider call log (offline tests).
    calls = getattr(source, "calls", None)
    if calls:
        blob = json.dumps(calls, default=str)
        if tool_name in blob:
            return

    raise AssertionError(f"tool '{tool_name}' was never called")


# ── latency / tokens ─────────────────────────────────────────────────────────

class _Stopwatch:
    def __init__(self) -> None:
        self.seconds = 0.0


@contextmanager
def measure_latency() -> Iterator[_Stopwatch]:
    """Context manager timing the enclosed block (``.seconds``)."""
    watch = _Stopwatch()
    start = time.monotonic()
    try:
        yield watch
    finally:
        watch.seconds = time.monotonic() - start


def assert_latency_under(seconds: float, watch: _Stopwatch) -> None:
    """Assert a previously measured block ran within ``seconds``."""
    if watch.seconds > seconds:
        raise AssertionError(f"latency {watch.seconds:.2f}s exceeded budget {seconds:.2f}s")


def assert_tokens_under(limit: int, client: Any) -> None:
    """Assert an LLM client's cumulative token usage is under ``limit``."""
    usage = getattr(client, "total_usage", None)
    total = getattr(usage, "total_tokens", None)
    if total is None:
        raise AssertionError("client does not expose total_usage.total_tokens")
    if total > limit:
        raise AssertionError(f"token usage {total} exceeded budget {limit}")
