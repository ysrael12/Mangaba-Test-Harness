"""
LLM-as-judge scoring.

An optional, provider-agnostic evaluator: a (separate) LLM scores a response
against a rubric and returns a 0..1 score with reasoning. The judge model is
configurable like any other target — pass any ``LLMClient`` (real or mock).

Kept deterministic-testable: because it only depends on ``client.generate_text``,
a scripted mock client can drive it offline.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from mangaba_test.assertions.behavioral import extract_json

_JUDGE_TEMPLATE = (
    "You are a strict evaluator. Score how well the RESPONSE satisfies the "
    "RUBRIC for the given TASK.\n\n"
    "TASK:\n{task}\n\nRUBRIC:\n{rubric}\n\nRESPONSE:\n{response}\n\n"
    "Reply with ONLY a JSON object: "
    '{{"score": <float 0..1>, "reasoning": "<one sentence>"}}'
)


@dataclass
class JudgeResult:
    """Outcome of an LLM-judge evaluation."""

    score: float
    reasoning: str = ""
    raw: str = ""

    def __bool__(self) -> bool:  # truthy when score is meaningfully positive
        return self.score >= 0.5


class LLMJudge:
    """Scores responses 0..1 using a configurable LLM client."""

    def __init__(self, client: Any, *, template: Optional[str] = None) -> None:
        self.client = client
        self.template = template or _JUDGE_TEMPLATE

    def score(self, task: str, response: str, rubric: str) -> JudgeResult:
        prompt = self.template.format(task=task, response=response, rubric=rubric)
        raw = self.client.generate_text(prompt)
        try:
            data = extract_json(raw)
            score = float(data.get("score", 0.0))
        except (ValueError, TypeError, AttributeError):
            return JudgeResult(score=0.0, reasoning="unparseable judge output", raw=raw)
        score = max(0.0, min(1.0, score))
        return JudgeResult(score=score, reasoning=str(data.get("reasoning", "")), raw=raw)

    def assert_min_score(
        self,
        task: str,
        response: str,
        rubric: str,
        *,
        min_score: float = 0.7,
    ) -> JudgeResult:
        """Score and assert the result meets ``min_score``."""
        result = self.score(task, response, rubric)
        if result.score < min_score:
            raise AssertionError(
                f"judge score {result.score:.2f} < {min_score:.2f} "
                f"({result.reasoning or 'no reasoning'})"
            )
        return result
