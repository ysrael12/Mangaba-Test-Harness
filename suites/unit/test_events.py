"""Unit — EventBus (L0)."""

from __future__ import annotations

import pytest

from mangaba_test import compat

pytestmark = pytest.mark.unit


def _guard():
    if not compat.require("EventBus", "Event", "EventType"):
        pytest.skip(compat.missing("EventBus", "Event", "EventType"))


def test_emit_and_collect(event_collector):
    _guard()
    compat.EventBus.emit(compat.Event(event_type=compat.EventType.AGENT_START, data={"hi": 1}))
    assert len(event_collector.events) == 1
    assert event_collector.events[0].data["hi"] == 1


def test_unregister_stops_delivery():
    _guard()
    if compat.BaseCallback is None:
        pytest.skip(compat.missing("BaseCallback"))

    received = []

    class C(compat.BaseCallback):  # type: ignore[misc, valid-type]
        def on_event(self, event):
            received.append(event)

    c = C()
    compat.EventBus.register(c)
    compat.EventBus.unregister(c)
    compat.EventBus.emit(compat.Event(event_type=compat.EventType.AGENT_END))
    assert received == []
