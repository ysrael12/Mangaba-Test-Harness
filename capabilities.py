"""
Per-(provider, model) capability detection.

Lets suites gate themselves: a tool-calling test must be skipped/xfailed for a
model that cannot do native function calling (e.g. ``meta-llama/Meta-Llama-3-8B``,
flagged ``tool_calling: False`` in the framework's ``HF_OPEN_MODELS`` catalogue).

Capabilities are resolved defensively — when the framework does not expose the
needed metadata, we assume the capability is present (``True``) so newer/unknown
models are not falsely skipped.
"""

from __future__ import annotations

from typing import Optional

from mangaba_test import compat

# Providers whose native SDK path supports tool/function calling for all models.
_NATIVE_TOOL_PROVIDERS = {"google", "openai", "anthropic", "openrouter", "mock"}

# Provider name aliases → canonical provider name.
_ALIASES = {
    "gemini": "google", "google-ai": "google", "googleai": "google",
    "gpt": "openai", "chatgpt": "openai",
    "claude": "anthropic",
    "hf": "huggingface", "hugging-face": "huggingface",
    "or": "openrouter", "open-router": "openrouter",
    "fake": "mock", "dummy": "mock",
}


def canonical_provider(provider: str) -> str:
    """Normalise a provider name/alias to its canonical form."""
    p = (provider or "").lower().strip()
    return _ALIASES.get(p, p)


def supports_tools(provider: str, model: str) -> bool:
    """Whether (provider, model) supports native tool/function calling."""
    prov = canonical_provider(provider)
    if prov == "huggingface" and compat.hf_model_supports_tools is not None:
        try:
            return bool(compat.hf_model_supports_tools(model))
        except Exception:
            return True
    return prov in _NATIVE_TOOL_PROVIDERS


def supports_streaming(provider: str, model: str) -> bool:
    """All current providers expose a streaming path; default True."""
    return True


def context_window(provider: str, model: str) -> Optional[int]:
    """Context window for a HuggingFace catalogue model, else ``None``."""
    if canonical_provider(provider) == "huggingface" and compat.HF_OPEN_MODELS:
        for entry in compat.HF_OPEN_MODELS:
            if entry.get("id") == model:
                return entry.get("context")
    return None
