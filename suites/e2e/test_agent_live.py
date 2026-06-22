"""
E2E — real provider runs. Requires a configured target + API key.

Skips automatically when run offline (mock target) or without a key, so these
never break a no-network CI lane. Tool-calling tests are capability-gated.
"""

from __future__ import annotations

import pytest

from mangaba_test import compat
from mangaba_test.assertions import (
    assert_contains_any,
    assert_no_pii_leaked,
    assert_tool_was_called,
)
from mangaba_test.plan import Target

pytestmark = pytest.mark.e2e


def _require_real(target: Target):
    if target.provider == "mock":
        pytest.skip("e2e requires a real provider target (got mock)")


def test_agent_answers_live(llm_client, active_target):
    _require_real(active_target)
    if compat.Agent is None:
        pytest.skip(compat.missing("Agent"))
    agent = compat.Agent(
        role="Concise Assistant",
        goal="Answer in a single short sentence",
        backstory="You answer factual questions briefly.",
        llm=llm_client,
    )
    answer = agent.execute_task("What is the capital of France? Answer in one word.")
    assert isinstance(answer, str) and answer.strip()
    assert_contains_any(answer, ["paris"])
    assert_no_pii_leaked(answer)


def test_tool_calling_live(llm_client, active_target, skip_without_tools, event_collector):
    _require_real(active_target)
    if not compat.require("Agent", "CalculatorTool"):
        pytest.skip(compat.missing("Agent", "CalculatorTool"))
    agent = compat.Agent(
        role="Math Assistant",
        goal="Use the calculator tool for arithmetic",
        backstory="You always use tools for math.",
        tools=[compat.CalculatorTool()],
        llm=llm_client,
    )
    answer = agent.execute_task("Use the calculator to compute 123 * 7.")
    assert_tool_was_called(event_collector, "calculator")
    assert_contains_any(answer, ["861"])


def test_response_quality_judged(llm_client, active_target, llm_judge):
    """Opt-in: scores answer quality with a configured LLM judge (MTH_JUDGE)."""
    _require_real(active_target)
    if compat.Agent is None:
        pytest.skip(compat.missing("Agent"))
    agent = compat.Agent(
        role="Geography Tutor",
        goal="Explain clearly",
        backstory="You give correct, concise explanations.",
        llm=llm_client,
    )
    answer = agent.execute_task("Why is the sky blue? One sentence.")
    llm_judge.assert_min_score(
        task="Explain why the sky is blue in one sentence.",
        response=answer,
        rubric="Mentions scattering of light (Rayleigh) and is concise.",
        min_score=0.5,
    )
