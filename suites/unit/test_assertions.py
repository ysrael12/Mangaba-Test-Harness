"""Unit — the harness's own behavioral assertions and LLM judge (offline)."""

from __future__ import annotations

import time

import pytest

from mangaba_test.assertions import (
    assert_contains_any,
    assert_is_valid_json,
    assert_latency_under,
    assert_no_pii_leaked,
    assert_tool_was_called,
    extract_json,
    measure_latency,
)
from mangaba_test.assertions.judge import LLMJudge

pytestmark = pytest.mark.unit


# ── content ──────────────────────────────────────────────────────────────────

def test_contains_any_passes_and_fails():
    assert_contains_any("The capital is Paris.", ["paris", "lisbon"])
    with pytest.raises(AssertionError):
        assert_contains_any("nope", ["paris"])


def test_extract_json_from_fenced_block():
    assert extract_json('Here:\n```json\n{"a": 1}\n```') == {"a": 1}


def test_is_valid_json_with_prose_around():
    assert assert_is_valid_json('result: [1, 2, 3] done') == [1, 2, 3]


def test_no_pii_leaked_detects_email():
    assert_no_pii_leaked("all clean here")
    with pytest.raises(AssertionError):
        assert_no_pii_leaked("contact me at john@example.com")


# ── tool usage ────────────────────────────────────────────────────────────────

class _FakeEvent:
    def __init__(self, data):
        self.data = data


def test_tool_was_called_via_event_stream():
    events = [_FakeEvent({"tool": "calculator"})]
    assert_tool_was_called(events, "calculator")
    with pytest.raises(AssertionError):
        assert_tool_was_called(events, "search")


def test_tool_was_called_via_react_action_payload():
    events = [_FakeEvent({"tool_calls": [{"tool_name": "search", "arguments": {}}]})]
    assert_tool_was_called(events, "search")


# ── latency ────────────────────────────────────────────────────────────────────

def test_measure_latency_and_budget():
    with measure_latency() as w:
        time.sleep(0.01)
    assert w.seconds > 0
    assert_latency_under(5.0, w)
    with pytest.raises(AssertionError):
        assert_latency_under(0.0, w)


# ── judge (offline, scripted mock) ──────────────────────────────────────────────

def test_llm_judge_scores_from_mock(mock_client):
    judge = LLMJudge(mock_client(script=[{"text": '{"score": 0.9, "reasoning": "great"}'}]))
    result = judge.score("Q", "A", "must be great")
    assert result.score == 0.9
    assert result.reasoning == "great"


def test_llm_judge_assert_min_score_raises_when_low(mock_client):
    judge = LLMJudge(mock_client(script=[{"text": '{"score": 0.3, "reasoning": "weak"}'}]))
    with pytest.raises(AssertionError):
        judge.assert_min_score("Q", "A", "rubric", min_score=0.7)


def test_llm_judge_handles_unparseable(mock_client):
    judge = LLMJudge(mock_client(script=[{"text": "not json at all"}]))
    assert judge.score("Q", "A", "r").score == 0.0
