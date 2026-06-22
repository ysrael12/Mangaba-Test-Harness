"""
Deterministic LLM provider for offline (no-network) tests.

``MockLLMProvider`` subclasses the framework's ``BaseLLMProvider`` and replays a
scripted sequence of responses, including tool calls. It is what makes the
``reasoning`` / ``agent`` / ``crew`` integration suites deterministic without any
API key or network access.

The provider is registered into the framework ``PROVIDERS`` registry under the
name ``"mock"`` (idempotently) so it can be built through the regular
``create_llm_client("mock", ...)`` factory path.

Script step formats::

    {"text": "final answer"}                       # -> STOP response
    {"tool_calls": [                                # -> TOOL_CALLS response
        {"tool_name": "calculator",
         "arguments": {"expression": "2+2"}},
    ]}

If the script is exhausted, ``default_text`` is returned. Pass ``raise_error`` to
simulate provider failures (e.g. ``RateLimitError``).
"""

from __future__ import annotations

from typing import Any, Dict, Iterator, List, Optional

from mangaba_test import compat


def _build_response(step: Dict[str, Any], model: str) -> Any:
    """Translate a script step into a framework ``LLMResponse``."""
    tool_calls_spec = step.get("tool_calls")
    if tool_calls_spec and compat.ToolCall is not None:
        calls = [
            compat.ToolCall(
                tool_name=c["tool_name"],
                arguments=c.get("arguments", {}),
            )
            for c in tool_calls_spec
        ]
        finish = getattr(compat.FinishReason, "TOOL_CALLS", None)
        kwargs: Dict[str, Any] = {
            "content": step.get("text", ""),
            "tool_calls": calls,
            "model": model,
        }
        if finish is not None:
            kwargs["finish_reason"] = finish
        return compat.LLMResponse(**kwargs)

    return compat.LLMResponse(content=step.get("text", ""), model=model)


def _make_mock_class() -> Optional[type]:
    """Define ``MockLLMProvider`` against the installed ``BaseLLMProvider``."""
    base = compat.BaseLLMProvider
    if base is None or compat.LLMResponse is None:
        return None

    class MockLLMProvider(base):  # type: ignore[misc, valid-type]
        """Scriptable, deterministic provider — no network, no keys."""

        name = "mock"
        aliases = ("fake", "dummy")

        def __init__(
            self,
            api_key: str = "mock-key",
            model: str = "mock-model",
            *,
            script: Optional[List[Dict[str, Any]]] = None,
            default_text: str = "MOCK_RESPONSE",
            raise_error: Optional[BaseException] = None,
            **options: Any,
        ) -> None:
            super().__init__(api_key, model, **options)
            self._script: List[Dict[str, Any]] = list(script or [])
            self._default_text = default_text
            self._raise_error = raise_error
            self._index = 0
            # Inspectable call log for assertions in tests.
            self.calls: List[Dict[str, Any]] = []

        # -- script cursor ---------------------------------------------------

        def _next_step(self) -> Dict[str, Any]:
            if self._index < len(self._script):
                step = self._script[self._index]
                self._index += 1
                return step
            return {"text": self._default_text}

        def _maybe_raise(self) -> None:
            if self._raise_error is not None:
                raise self._raise_error

        # -- BaseLLMProvider contract ---------------------------------------

        def generate(self, prompt: str, **kwargs: Any) -> Any:
            self.calls.append({"kind": "generate", "prompt": prompt})
            self._maybe_raise()
            return _build_response(self._next_step(), self.model)

        def generate_with_tools(
            self,
            messages: List[Dict[str, Any]],
            tools: Optional[List[Any]] = None,
            **kwargs: Any,
        ) -> Any:
            self.calls.append({
                "kind": "generate_with_tools",
                "messages": messages,
                "tools": [getattr(t, "name", repr(t)) for t in (tools or [])],
            })
            self._maybe_raise()
            return _build_response(self._next_step(), self.model)

        def stream(self, prompt: str, **kwargs: Any) -> Iterator[str]:
            self.calls.append({"kind": "stream", "prompt": prompt})
            self._maybe_raise()
            text = self._next_step().get("text", self._default_text)
            for word in text.split():
                yield word + " "

        def count_tokens(self, text: str) -> int:
            return max(1, len(text) // 4)

    return MockLLMProvider


MockLLMProvider = _make_mock_class()


def register_mock_provider() -> bool:
    """Register ``MockLLMProvider`` into the framework registry. Idempotent.

    Best-effort: the standalone mock client does not depend on this, but it keeps
    ``create_llm_client("mock", ...)`` working where the registry is shared.
    """
    if MockLLMProvider is None or compat.PROVIDERS is None:
        return False
    try:
        compat.PROVIDERS.setdefault("mock", MockLLMProvider)
    except Exception:
        return False
    return True


class MockLLMClient:
    """Standalone, duck-typed mock of the framework's ``LLMClient``.

    Deliberately does **not** route through ``create_llm_client`` or the provider
    registry — those have moved/renamed across framework versions. It only needs
    the ``LLMResponse``/``ToolCall`` types and exposes the surface that
    ``Agent`` / ``ReActEngine`` / ``RAGChain`` / the LLM judge actually call:
    ``generate``, ``generate_text``, ``generate_with_tools``, ``stream``,
    ``count_tokens`` and ``total_usage``.
    """

    provider_name = "mock"

    def __init__(
        self,
        *,
        script: Optional[List[Dict[str, Any]]] = None,
        model: str = "mock-model",
        default_text: str = "MOCK_RESPONSE",
        raise_error: Optional[BaseException] = None,
        **options: Any,
    ) -> None:
        self.model = model
        self._script: List[Dict[str, Any]] = list(script or [])
        self._default_text = default_text
        self._raise_error = raise_error
        self._index = 0
        self.calls: List[Dict[str, Any]] = []
        self._usage = compat.TokenUsage() if compat.TokenUsage is not None else None

    def _next_step(self) -> Dict[str, Any]:
        if self._index < len(self._script):
            step = self._script[self._index]
            self._index += 1
            return step
        return {"text": self._default_text}

    def _maybe_raise(self) -> None:
        if self._raise_error is not None:
            raise self._raise_error

    def generate(self, prompt: str, **kwargs: Any) -> Any:
        self.calls.append({"kind": "generate", "prompt": prompt})
        self._maybe_raise()
        return _build_response(self._next_step(), self.model)

    def generate_text(self, prompt: str, **kwargs: Any) -> str:
        return self.generate(prompt, **kwargs).text

    def generate_with_tools(
        self,
        messages: List[Dict[str, Any]],
        tools: Optional[List[Any]] = None,
        **kwargs: Any,
    ) -> Any:
        self.calls.append({
            "kind": "generate_with_tools",
            "messages": messages,
            "tools": [getattr(t, "name", repr(t)) for t in (tools or [])],
        })
        self._maybe_raise()
        return _build_response(self._next_step(), self.model)

    def stream(self, prompt: str, **kwargs: Any) -> Iterator[str]:
        self.calls.append({"kind": "stream", "prompt": prompt})
        self._maybe_raise()
        text = self._next_step().get("text", self._default_text)
        for word in text.split():
            yield word + " "

    def count_tokens(self, text: str) -> int:
        return max(1, len(text) // 4)

    @property
    def total_usage(self) -> Any:
        return self._usage


def make_mock_client(
    *,
    script: Optional[List[Dict[str, Any]]] = None,
    model: str = "mock-model",
    default_text: str = "MOCK_RESPONSE",
    raise_error: Optional[BaseException] = None,
    **options: Any,
) -> MockLLMClient:
    """Build a standalone mock LLM client.

    Raises ``RuntimeError`` only if the framework lacks the ``LLMResponse`` type
    entirely (extremely old/broken). Callers (fixtures) convert that to a skip.
    """
    if compat.LLMResponse is None:
        raise RuntimeError(compat.missing("LLMResponse"))
    register_mock_provider()  # harmless best-effort; keeps the registry path usable
    return MockLLMClient(
        script=script,
        model=model,
        default_text=default_text,
        raise_error=raise_error,
        **options,
    )
