"""
Environment diagnostics: which providers are usable right now.

Reports, per provider: whether an API key is present in the environment and
whether the provider SDK is importable. Never prints key values.
"""

from __future__ import annotations

import importlib.util
from typing import List, Tuple

from mangaba_test import compat
from mangaba_test.factory import resolve_api_key

# provider → (canonical SDK import name)
_PROVIDER_SDK = {
    "google": "google.generativeai",
    "openai": "openai",
    "anthropic": "anthropic",
    "huggingface": "huggingface_hub",
    "openrouter": "openai",  # OpenRouter uses the OpenAI SDK
    "mock": None,
}


def _sdk_available(module_name: str | None) -> bool:
    if module_name is None:
        return True
    return importlib.util.find_spec(module_name) is not None


def diagnose() -> List[Tuple[str, bool, bool]]:
    """Return [(provider, has_key, sdk_installed)] for known providers."""
    providers: List[str] = []
    if compat.PROVIDERS is not None:
        providers = list(compat.PROVIDERS.keys())
    if "mock" not in providers:
        providers.append("mock")

    rows: List[Tuple[str, bool, bool]] = []
    for prov in providers:
        has_key = bool(resolve_api_key(prov))
        sdk = _sdk_available(_PROVIDER_SDK.get(prov, ""))
        rows.append((prov, has_key, sdk))
    return rows


def render() -> str:
    """Human-readable diagnostics table."""
    lines = [
        f"Mangaba Test Harness - doctor",
        f"  mangaba version : {compat.version or 'NOT INSTALLED'}",
        f"  core LLM client : {'ok' if compat.create_llm_client else 'MISSING'}",
        "",
        f"  {'provider':<14}{'api key':<10}{'sdk':<8}",
        f"  {'-'*12:<14}{'-'*8:<10}{'-'*6:<8}",
    ]
    for prov, has_key, sdk in diagnose():
        key_mark = "yes" if has_key else "-"
        sdk_mark = "yes" if sdk else "no"
        lines.append(f"  {prov:<14}{key_mark:<10}{sdk_mark:<8}")
    return "\n".join(lines)
