"""
LLM client construction and API-key resolution for the harness.

Key resolution follows the same environment-variable convention already used by
the project's ``config.py`` so a developer's existing ``.env`` works unchanged.
"""

from __future__ import annotations

import os
from typing import Any, List, Optional, Union

from mangaba_test import compat
from mangaba_test.capabilities import canonical_provider
from mangaba_test.fixtures.mock_provider import make_mock_client, register_mock_provider

# Ordered env-var candidates per provider (mirrors project config.py).
_API_KEY_ENV: dict[str, List[str]] = {
    "google": ["GOOGLE_API_KEY", "GEMINI_API_KEY"],
    "openai": ["OPENAI_API_KEY"],
    "anthropic": ["ANTHROPIC_API_KEY"],
    "huggingface": [
        "HUGGINGFACE_API_KEY", "HUGGINGFACE_TOKEN", "HF_TOKEN",
        "HUGGINGFACEHUB_API_TOKEN",
    ],
    "openrouter": ["OPENROUTER_API_KEY"],
    "mock": [],
}


def resolve_api_key(provider: str, api_key_env: Optional[str] = None) -> Optional[str]:
    """Resolve an API key from the environment for ``provider``.

    If ``api_key_env`` is given it takes priority; otherwise the provider's
    default candidate vars are tried in order, with ``API_KEY`` as last resort.
    """
    prov = canonical_provider(provider)
    if prov == "mock":
        return "mock-key"

    candidates: List[str] = []
    if api_key_env:
        candidates.append(api_key_env)
    candidates.extend(_API_KEY_ENV.get(prov, []))
    candidates.append("API_KEY")

    for var in candidates:
        value = os.getenv(var)
        if value:
            return value
    return None


def build_client(
    provider: str,
    model: Union[str, List[str]],
    *,
    api_key: Optional[str] = None,
    api_key_env: Optional[str] = None,
    **options: Any,
) -> Any:
    """Construct an ``LLMClient`` for ``(provider, model)``.

    The ``mock`` provider is handled offline (no key required). Real providers go
    through the framework's ``create_llm_client`` factory.
    """
    prov = canonical_provider(provider)

    if prov == "mock":
        register_mock_provider()
        model_name = model if isinstance(model, str) else (model[0] if model else "mock-model")
        return make_mock_client(model=model_name, **options)

    if compat.create_llm_client is None:
        raise RuntimeError(compat.missing("create_llm_client"))

    key = api_key or resolve_api_key(provider, api_key_env)
    if not key:
        raise MissingApiKeyError(provider, api_key_env)

    return compat.create_llm_client(provider=provider, api_key=key, model=model, **options)


class MissingApiKeyError(RuntimeError):
    """Raised when no API key is available for a real provider."""

    def __init__(self, provider: str, api_key_env: Optional[str] = None) -> None:
        self.provider = provider
        env_hint = api_key_env or ", ".join(_API_KEY_ENV.get(canonical_provider(provider), [])) or "API_KEY"
        super().__init__(f"No API key for provider '{provider}' (set one of: {env_hint})")
