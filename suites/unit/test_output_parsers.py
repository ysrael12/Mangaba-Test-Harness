"""Unit — output parsers (L1)."""

from __future__ import annotations

import pytest

from mangaba_test import compat

pytestmark = pytest.mark.unit


def test_json_parser_plain():
    if compat.JSONOutputParser is None:
        pytest.skip(compat.missing("JSONOutputParser"))
    assert compat.JSONOutputParser().parse('{"key": "value"}') == {"key": "value"}


def test_json_parser_markdown_fenced():
    if compat.JSONOutputParser is None:
        pytest.skip(compat.missing("JSONOutputParser"))
    parsed = compat.JSONOutputParser().parse('```json\n{"key": "value"}\n```')
    assert parsed == {"key": "value"}


def test_list_parser():
    if compat.ListOutputParser is None:
        pytest.skip(compat.missing("ListOutputParser"))
    items = compat.ListOutputParser().parse("- item1\n- item2\n- item3")
    assert len(items) == 3
