"""Unit — guardrails (L1)."""

from __future__ import annotations

import pytest

from mangaba_test import compat

pytestmark = pytest.mark.unit


def test_length_guardrail_passes_short_text():
    if compat.LengthGuardrail is None:
        pytest.skip(compat.missing("LengthGuardrail"))
    g = compat.LengthGuardrail(max_length=100)
    assert g.validate("short text") == "short text"


def test_length_guardrail_truncates():
    if compat.LengthGuardrail is None:
        pytest.skip(compat.missing("LengthGuardrail"))
    g = compat.LengthGuardrail(max_length=5)
    assert len(g.validate("this is too long")) == 5


def test_content_filter_redacts():
    if compat.ContentFilterGuardrail is None:
        pytest.skip(compat.missing("ContentFilterGuardrail"))
    g = compat.ContentFilterGuardrail(blocked_patterns=[r"spam"])
    assert g.validate("hello world") == "hello world"
    assert "spam" not in g.validate("this is spam content")
