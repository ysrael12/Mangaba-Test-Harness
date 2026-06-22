"""Unit — MCP and A2A protocols (L1)."""

from __future__ import annotations

import pytest

from mangaba_test import compat

pytestmark = pytest.mark.unit


def test_mcp_add_find_by_tag():
    if not compat.require("MCPProtocol", "MCPContext", "ContextType"):
        pytest.skip(compat.missing("MCPProtocol", "MCPContext", "ContextType"))
    proto = compat.MCPProtocol(max_contexts=10)
    ctx = compat.MCPContext.create(
        context_type=compat.ContextType.KNOWLEDGE,
        content={"topic": "AI"},
        tags=["ai"],
    )
    proto.add_context(ctx)
    found = proto.find_contexts_by_tag("ai")
    assert any(c.id == ctx.id for c in found)


def test_a2a_request_response_roundtrip():
    if compat.A2AProtocol is None:
        pytest.skip(compat.missing("A2AProtocol"))
    proto = compat.A2AProtocol("agent-1")
    msg = proto.create_request("agent-2", "ping", {"n": 1})
    assert msg.sender_id == "agent-1"
    assert msg.receiver_id == "agent-2"
    assert msg.content["action"] == "ping"
