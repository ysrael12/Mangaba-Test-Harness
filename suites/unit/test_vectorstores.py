"""Unit — in-memory vector store + factory registry (L1)."""

from __future__ import annotations

import pytest

from mangaba_test import compat

pytestmark = pytest.mark.unit


def test_factory_creates_inmemory():
    if compat.create_vectorstore is None:
        pytest.skip(compat.missing("create_vectorstore"))
    store = compat.create_vectorstore("inmemory")
    assert store is not None
    assert store.count == 0


def test_inmemory_add_search_clear():
    if compat.InMemoryVectorStore is None:
        pytest.skip(compat.missing("InMemoryVectorStore"))
    store = compat.InMemoryVectorStore()
    store.add(["hello", "world"], [[1.0, 0.0], [0.0, 1.0]])
    assert store.count == 2
    hits = store.search([1.0, 0.0], top_k=1)
    assert hits and "content" in hits[0]
    store.clear()
    assert store.count == 0
