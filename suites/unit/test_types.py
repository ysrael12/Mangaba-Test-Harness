"""Unit — core type models (L0). Version-resilient via compat."""

from __future__ import annotations

import pytest

from mangaba_test import compat

pytestmark = pytest.mark.unit


def test_llm_config_defaults():
    if compat.LLMConfig is None:
        pytest.skip(compat.missing("LLMConfig"))
    cfg = compat.LLMConfig(api_key="k", provider="google")
    assert 0.0 <= cfg.temperature <= 2.0
    assert cfg.max_tokens >= 1


def test_provider_alias_normalised():
    if compat.LLMConfig is None:
        pytest.skip(compat.missing("LLMConfig"))
    cfg = compat.LLMConfig(api_key="k", provider="gemini")
    assert cfg.provider == "google"


def test_llm_response_tool_calls_flag():
    if compat.LLMResponse is None or compat.ToolCall is None:
        pytest.skip(compat.missing("LLMResponse", "ToolCall"))
    tc = compat.ToolCall(tool_name="fn", arguments={"x": 1})
    resp = compat.LLMResponse(content="", tool_calls=[tc])
    assert resp.has_tool_calls is True
    assert compat.LLMResponse(content="hi").has_tool_calls is False


def test_openrouter_config_accepts_model_list():
    if compat.OpenRouterConfig is None:
        pytest.skip(compat.missing("OpenRouterConfig"))
    models = ["google/gemini-2.5-flash", "anthropic/claude-3.5-sonnet"]
    cfg = compat.OpenRouterConfig(model=models, api_key="sk-or-test")
    assert cfg.model == models
