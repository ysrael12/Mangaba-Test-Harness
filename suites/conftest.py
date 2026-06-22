"""
Shared pytest fixtures for all harness suites.

These fixtures are version-resilient: they skip (rather than error) when the
installed ``mangaba`` lacks a required symbol, and they build the LLM client from
the active :class:`TestPlan` target (mock by default, real provider under e2e).
"""

from __future__ import annotations

import os
from typing import Any, Callable, Dict, List, Optional

import pytest

from mangaba_test import capabilities, compat
from mangaba_test.assertions.judge import LLMJudge
from mangaba_test.factory import MissingApiKeyError, build_client
from mangaba_test.fixtures.mock_provider import make_mock_client, register_mock_provider
from mangaba_test.plan import TestPlan, Target


def pytest_configure(config: pytest.Config) -> None:
    for marker in (
        "unit: pure single-module tests (no network)",
        "contract: provider contract conformance",
        "integration: cross-module wiring (mock LLM by default)",
        "e2e: real provider end-to-end runs",
        "requires_tools: needs a model with native tool calling",
    ):
        config.addinivalue_line("markers", marker)


@pytest.fixture(autouse=True)
def _reset_event_bus():
    """Isolate the global EventBus between tests when present."""
    compat.reset_event_bus()
    yield
    compat.reset_event_bus()


@pytest.fixture(scope="session")
def active_target() -> Target:
    """The (provider, model) target for this run; defaults to mock."""
    plan = TestPlan.from_env()
    if plan and plan.primary:
        return plan.primary
    register_mock_provider()
    return Target(provider="mock", model="mock-model")


@pytest.fixture
def mock_client() -> Callable[..., Any]:
    """Factory: build a scripted standalone mock LLM client.

    Example::

        client = mock_client(script=[{"text": "hi"}])
    """
    if compat.LLMResponse is None:
        pytest.skip(compat.missing("LLMResponse"))

    def _factory(*, script: Optional[List[Dict[str, Any]]] = None, **kw: Any) -> Any:
        return make_mock_client(script=script, **kw)

    return _factory


@pytest.fixture
def llm_client(active_target: Target) -> Any:
    """Build the LLM client for the active target.

    Always degrades to a *skip* (never an error): a missing API key, a missing
    framework factory, or a too-old framework all skip cleanly so an incomplete
    or refactored environment never produces hard failures.
    """
    if active_target.provider == "mock":
        if compat.LLMResponse is None:
            pytest.skip(compat.missing("LLMResponse"))
    elif compat.create_llm_client is None:
        pytest.skip(compat.missing("create_llm_client"))
    try:
        return build_client(
            active_target.provider,
            active_target.model,
            api_key_env=active_target.api_key_env,
            **active_target.options,
        )
    except MissingApiKeyError as exc:
        pytest.skip(str(exc))
    except RuntimeError as exc:
        pytest.skip(str(exc))


@pytest.fixture
def event_collector():
    """Collect EventBus events emitted during a test."""
    if compat.EventBus is None or compat.BaseCallback is None:
        pytest.skip(compat.missing("EventBus", "BaseCallback"))

    class _Collector(compat.BaseCallback):  # type: ignore[misc, valid-type]
        def __init__(self) -> None:
            super().__init__()
            self.events: list = []

        def on_event(self, event) -> None:
            self.events.append(event)

        def types(self) -> list:
            return [getattr(e.event_type, "value", e.event_type) for e in self.events]

    collector = _Collector()
    compat.EventBus.register(collector)
    return collector


# ── capability gating helper ────────────────────────────────────────────────

@pytest.fixture
def llm_judge():
    """An optional LLM-as-judge, configured via ``MTH_JUDGE=provider:model``.

    Skips when unset or when the judge provider has no API key — judge-based
    assertions are opt-in and never block an unconfigured run.
    """
    spec = os.getenv("MTH_JUDGE")
    if not spec:
        pytest.skip("no judge configured (set MTH_JUDGE=provider:model)")
    provider, _, model = spec.partition(":")
    try:
        client = build_client(provider, model or "mock-model")
    except MissingApiKeyError as exc:
        pytest.skip(str(exc))
    return LLMJudge(client)


@pytest.fixture
def skip_without_tools(active_target: Target):
    """Skip the test if the active model lacks native tool calling."""
    if not capabilities.supports_tools(active_target.provider, active_target.model):
        pytest.skip(
            f"model '{active_target.model_label}' on '{active_target.provider}' "
            f"has no native tool calling"
        )
