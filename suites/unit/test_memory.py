"""Unit — short-term memory (L1)."""

from __future__ import annotations

import pytest

from mangaba_test import compat

pytestmark = pytest.mark.unit


def test_add_and_search():
    if compat.ShortTermMemory is None:
        pytest.skip(compat.missing("ShortTermMemory"))
    mem = compat.ShortTermMemory(max_items=10)
    mem.add("Python is great")
    mem.add("Java is verbose")
    results = mem.search("Python")
    assert any("Python" in r.get("content", "") for r in results)


def test_max_items_eviction():
    if compat.ShortTermMemory is None:
        pytest.skip(compat.missing("ShortTermMemory"))
    mem = compat.ShortTermMemory(max_items=2)
    for item in ("a", "b", "c"):
        mem.add(item)
    assert len(mem.get_all()) == 2
