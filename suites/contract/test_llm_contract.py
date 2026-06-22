"""
Contract — every provider must honour the ``BaseLLMProvider`` interface.

Shape checks run against whatever target is active (``mock`` offline by default,
a real provider under e2e). Tool-call *semantics* are asserted against the
deterministic mock so they need no network.
"""

from __future__ import annotations

import pytest

from mangaba_test import compat

pytestmark = pytest.mark.contract


def test_generate_returns_llm_response(llm_client):
    resp = llm_client.generate("Say hello in one word.")
    assert resp is not None
    assert isinstance(resp.text, str)
    # usage object is always present in the standard response
    assert hasattr(resp, "usage")


def test_count_tokens_is_positive_int(llm_client):
    n = llm_client.count_tokens("hello world")
    assert isinstance(n, int) and n >= 1


def test_stream_yields_strings(llm_client):
    chunks = list(llm_client.stream("hello"))
    assert chunks, "stream produced no chunks"
    assert all(isinstance(c, str) for c in chunks)


def test_tool_call_response_shape(mock_client):
    """A scripted tool call must surface as ToolCall objects."""
    if compat.ToolCall is None:
        pytest.skip(compat.missing("ToolCall"))
    client = mock_client(script=[
        {"tool_calls": [{"tool_name": "calculator", "arguments": {"expression": "2+2"}}]},
    ])
    resp = client.generate_with_tools(
        messages=[{"role": "user", "content": "2+2?"}],
        tools=[],
    )
    assert resp.has_tool_calls
    call = resp.tool_calls[0]
    assert call.tool_name == "calculator"
    assert call.arguments == {"expression": "2+2"}


def test_provider_registry_is_exposed():
    if compat.PROVIDERS is None:
        pytest.skip(compat.missing("PROVIDERS"))
    # Every registered provider class must declare the contract surface.
    for name, cls in compat.PROVIDERS.items():
        for method in ("generate", "generate_with_tools", "stream", "count_tokens"):
            assert hasattr(cls, method), f"provider '{name}' missing {method}()"
