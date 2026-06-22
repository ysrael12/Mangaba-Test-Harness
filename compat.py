"""
Version-resilient access layer to the ``mangaba`` framework.

Every symbol the harness needs is resolved here through :func:`_imp`, which
returns ``None`` when the symbol is absent from the installed framework version.
Suites consult :func:`require` / :func:`missing` and skip gracefully instead of
raising ``ImportError`` — this is what lets one test base cover several
``mangaba`` releases.

Usage::

    from mangaba_test import compat

    if compat.Agent is None:
        pytest.skip(compat.missing("Agent"))
    agent = compat.Agent(role="...", ...)
"""

from __future__ import annotations

import importlib
import re
from typing import Any, Optional, Tuple, Union


def _imp(module_paths: Union[str, Tuple[str, ...]], name: str) -> Optional[Any]:
    """Import ``name`` from the first candidate module that provides it.

    ``module_paths`` may be a single dotted path or a tuple of candidates. This
    tolerates **module relocation** across framework versions (e.g. a symbol that
    moved from ``mangaba.core.llm.client`` to ``mangaba.core.llm.providers``):
    we return the first match and ``None`` only if no candidate has it.
    """
    if isinstance(module_paths, str):
        module_paths = (module_paths,)
    for path in module_paths:
        try:
            module = importlib.import_module(path)
        except Exception:
            continue
        obj = getattr(module, name, None)
        if obj is not None:
            return obj
    return None


# Candidate module paths for the LLM layer, covering historical and refactored
# layouts (symbols have moved between client/base/providers/llm_factory across
# versions). ``_imp`` scans these in order.
_LLM_PATHS: Tuple[str, ...] = (
    "mangaba.core.llm.client",
    "mangaba.core.llm.llm_factory",
    "mangaba.core.llm.providers",
    "mangaba.core.llm.base",
    "mangaba.core.llm",
    "mangaba",
)
_SCHEMA_PATHS: Tuple[str, ...] = _LLM_PATHS + (
    "mangaba.core.llm.providers.schemas",
)


# ── Framework version ──────────────────────────────────────────────────────

def _detect_version() -> Optional[str]:
    pkg = _imp("mangaba", "__version__")
    return pkg if isinstance(pkg, str) else None


version: Optional[str] = _detect_version()


def version_tuple() -> Tuple[int, ...]:
    """Best-effort numeric version tuple, e.g. ``(3, 3, 0)``. ``()`` if unknown."""
    if not version:
        return ()
    nums = re.findall(r"\d+", version)
    return tuple(int(n) for n in nums) if nums else ()


# ── Core types ─────────────────────────────────────────────────────────────

LLMResponse = _imp("mangaba.core.types", "LLMResponse")
ToolCall = _imp("mangaba.core.types", "ToolCall")
ToolResult = _imp("mangaba.core.types", "ToolResult")
TokenUsage = _imp("mangaba.core.types", "TokenUsage")
FinishReason = _imp("mangaba.core.types", "FinishReason")
Message = _imp("mangaba.core.types", "Message")
LLMConfig = _imp("mangaba.core.types", "LLMConfig")
OpenRouterConfig = _imp("mangaba.core.types", "OpenRouterConfig")

# ── Exceptions ─────────────────────────────────────────────────────────────

MangabaError = _imp("mangaba.core.exceptions", "MangabaError")
LLMError = _imp("mangaba.core.exceptions", "LLMError")
RateLimitError = _imp("mangaba.core.exceptions", "RateLimitError")
AuthenticationError = _imp("mangaba.core.exceptions", "AuthenticationError")
ToolError = _imp("mangaba.core.exceptions", "ToolError")
AgentError = _imp("mangaba.core.exceptions", "AgentError")
CrewError = _imp("mangaba.core.exceptions", "CrewError")
MaxIterationsError = _imp("mangaba.core.exceptions", "MaxIterationsError")

# ── LLM layer ──────────────────────────────────────────────────────────────

BaseLLMProvider = _imp(_LLM_PATHS, "BaseLLMProvider")
PROVIDERS = _imp(_LLM_PATHS, "PROVIDERS")
LLMClient = _imp(_LLM_PATHS, "LLMClient")
create_llm_client = _imp(_LLM_PATHS, "create_llm_client")
get_supported_providers = _imp(_LLM_PATHS, "get_supported_providers")
hf_model_supports_tools = _imp(_LLM_PATHS, "hf_model_supports_tools")
list_huggingface_models = _imp(_LLM_PATHS, "list_huggingface_models")
HF_OPEN_MODELS = _imp(_LLM_PATHS, "HF_OPEN_MODELS")

# Provider-specific tool-schema converters (module-level helpers).
tool_to_openai_schema = _imp(_SCHEMA_PATHS, "_tool_to_openai_schema")
tool_to_google_declaration = _imp(_SCHEMA_PATHS, "_tool_to_google_declaration")
tool_to_anthropic_schema = _imp(_SCHEMA_PATHS, "_tool_to_anthropic_schema")

# ── Reasoning / orchestration ──────────────────────────────────────────────

ReActEngine = _imp("mangaba.core.reasoning", "ReActEngine")
Agent = _imp("mangaba.core.agent", "Agent")
Task = _imp("mangaba.core.task", "Task")
Crew = _imp("mangaba.core.crew", "Crew")
Process = _imp("mangaba.core.crew", "Process")
Pipeline = _imp("mangaba.core.workflow", "Pipeline")
Stage = _imp("mangaba.core.workflow", "Stage")

# ── Events ─────────────────────────────────────────────────────────────────

EventBus = _imp("mangaba.core.events", "EventBus")
Event = _imp("mangaba.core.events", "Event")
EventType = _imp("mangaba.core.events", "EventType")
BaseCallback = _imp("mangaba.core.events", "BaseCallback")

# ── Tools ──────────────────────────────────────────────────────────────────

BaseTool = _imp("mangaba.tools.base", "BaseTool")
tool = _imp("mangaba.tools.decorator", "tool")
CalculatorTool = _imp("mangaba.tools.math_tools", "CalculatorTool")
WordCounterTool = _imp("mangaba.tools.text_tools", "WordCounterTool")

# ── Guardrails / parsers ───────────────────────────────────────────────────

LengthGuardrail = _imp("mangaba.core.guardrails", "LengthGuardrail")
ContentFilterGuardrail = _imp("mangaba.core.guardrails", "ContentFilterGuardrail")
GuardrailChain = _imp("mangaba.core.guardrails", "GuardrailChain")
JSONOutputParser = _imp("mangaba.core.output_parsers", "JSONOutputParser")
ListOutputParser = _imp("mangaba.core.output_parsers", "ListOutputParser")

# ── Memory / vectorstores ──────────────────────────────────────────────────

ShortTermMemory = _imp("mangaba.memory.short_term", "ShortTermMemory")
create_vectorstore = _imp("mangaba.vectorstores.factory", "create_vectorstore")
InMemoryVectorStore = _imp("mangaba.vectorstores.in_memory", "InMemoryVectorStore")

# ── RAG ────────────────────────────────────────────────────────────────────

Document = _imp("mangaba.rag.document", "Document")
RecursiveTextSplitter = _imp("mangaba.rag.splitters", "RecursiveTextSplitter")
RAGChain = _imp("mangaba.rag.chain", "RAGChain")

# ── Protocols ──────────────────────────────────────────────────────────────

# Protocols live at the top level historically, but forks relocate them under
# the package (e.g. mangaba.protocols.*). Scan both.
_A2A_PATHS: Tuple[str, ...] = ("protocols.a2a", "mangaba.protocols.a2a", "mangaba.core.protocols.a2a")
_MCP_PATHS: Tuple[str, ...] = ("protocols.mcp", "mangaba.protocols.mcp", "mangaba.core.protocols.mcp")

A2AProtocol = _imp(_A2A_PATHS, "A2AProtocol")
MCPProtocol = _imp(_MCP_PATHS, "MCPProtocol")
MCPContext = _imp(_MCP_PATHS, "MCPContext")
ContextType = _imp(_MCP_PATHS, "ContextType")
ContextPriority = _imp(_MCP_PATHS, "ContextPriority")


# ── Helpers ────────────────────────────────────────────────────────────────

def require(*names: str) -> bool:
    """Return True only if every named compat symbol resolved (is not None)."""
    return all(globals().get(n) is not None for n in names)


def missing(*names: str) -> str:
    """Human-readable skip reason listing which symbols are absent."""
    absent = [n for n in names if globals().get(n) is None]
    return (
        f"requires mangaba symbols not present in v{version or '?'}: "
        f"{', '.join(absent)}"
    )


def reset_event_bus() -> None:
    """Reset the global EventBus if the framework exposes one."""
    if EventBus is not None and hasattr(EventBus, "reset"):
        EventBus.reset()
