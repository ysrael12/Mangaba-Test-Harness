"""
Integration — ReAct loop (L3) with a deterministic mock LLM.

Validates the Thought→Action→Observation cycle: a scripted tool call is executed
against a real tool, then a final answer is returned — all offline.
"""

from __future__ import annotations

import pytest

from mangaba_test import compat

pytestmark = pytest.mark.integration


def _guard():
    if not compat.require("ReActEngine", "CalculatorTool"):
        pytest.skip(compat.missing("ReActEngine", "CalculatorTool"))


def test_react_executes_tool_then_answers(mock_client):
    _guard()
    client = mock_client(script=[
        {"tool_calls": [{"tool_name": "calculator", "arguments": {"expression": "2+2"}}]},
        {"text": "The answer is 4."},
    ])
    engine = compat.ReActEngine(llm=client, tools=[compat.CalculatorTool()], max_iterations=5)
    result = engine.run(system_prompt="You are a calculator.", user_prompt="What is 2+2?")
    assert "4" in result.text


def test_react_direct_answer_without_tools(mock_client):
    _guard()
    client = mock_client(script=[{"text": "Paris"}])
    engine = compat.ReActEngine(llm=client, tools=[], max_iterations=3)
    result = engine.run(system_prompt="You are helpful.", user_prompt="Capital of France?")
    assert "Paris" in result.text


def test_react_emits_action_events(mock_client, event_collector):
    _guard()
    client = mock_client(script=[
        {"tool_calls": [{"tool_name": "calculator", "arguments": {"expression": "1+1"}}]},
        {"text": "2"},
    ])
    engine = compat.ReActEngine(llm=client, tools=[compat.CalculatorTool()], max_iterations=5)
    engine.run(system_prompt="calc", user_prompt="1+1?")
    assert any("tool" in t or "action" in t for t in event_collector.types())
