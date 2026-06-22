"""
Integration — Agent (L4) wiring reasoning + tools + memory, with a mock LLM.
"""

from __future__ import annotations

import pytest

from mangaba_test import compat

pytestmark = pytest.mark.integration


def _make_agent(client, tools=None):
    return compat.Agent(
        role="Test Analyst",
        goal="Answer questions accurately",
        backstory="A deterministic agent used in tests.",
        tools=tools or [],
        llm=client,
    )


def test_agent_executes_simple_task(mock_client):
    if compat.Agent is None:
        pytest.skip(compat.missing("Agent"))
    client = mock_client(script=[{"text": "Brasília is the capital."}])
    agent = _make_agent(client)
    result = agent.execute_task("What is the capital of Brazil?")
    assert "Brasília" in result


def test_agent_uses_tool(mock_client):
    if not compat.require("Agent", "CalculatorTool"):
        pytest.skip(compat.missing("Agent", "CalculatorTool"))
    client = mock_client(script=[
        {"tool_calls": [{"tool_name": "calculator", "arguments": {"expression": "21*2"}}]},
        {"text": "The result is 42."},
    ])
    agent = _make_agent(client, tools=[compat.CalculatorTool()])
    result = agent.execute_task("Compute 21 times 2.")
    assert "42" in result


def test_agent_persists_memory(mock_client):
    if compat.Agent is None:
        pytest.skip(compat.missing("Agent"))
    client = mock_client(default_text="noted")
    agent = _make_agent(client)
    agent.execute_task("Remember that the sky is blue.")
    # Default short-term memory should now hold at least one entry.
    if agent.memory is not None:
        assert len(agent.memory.get_all()) >= 1
