"""
Contract — parametrized over every provider class in the framework registry.

These checks are offline (no instantiation, no network): they assert that each
registered provider declares the ``BaseLLMProvider`` surface, resolves its own
name/aliases via ``matches()``, and that the provider-specific tool-schema
converters emit the correct shape. This is the provider-agnostic half of the
contract; the live half lives in the e2e suite (parametrized by real models).
"""

from __future__ import annotations

import pytest

from mangaba_test import compat

pytestmark = pytest.mark.contract

_REQUIRED_METHODS = ("generate", "generate_with_tools", "stream", "count_tokens")


def _provider_items():
    if compat.PROVIDERS is None:
        return []
    return sorted(compat.PROVIDERS.items(), key=lambda kv: kv[0])


def _provider_ids():
    return [name for name, _ in _provider_items()]


@pytest.fixture(scope="module")
def _registry_guard():
    if compat.PROVIDERS is None:
        pytest.skip(compat.missing("PROVIDERS"))


@pytest.mark.parametrize("provider_cls", [c for _, c in _provider_items()], ids=_provider_ids())
def test_provider_declares_contract_surface(_registry_guard, provider_cls):
    for method in _REQUIRED_METHODS:
        assert hasattr(provider_cls, method), f"{provider_cls.__name__} missing {method}()"


@pytest.mark.parametrize("name,provider_cls", _provider_items(), ids=_provider_ids())
def test_provider_matches_own_name_and_aliases(_registry_guard, name, provider_cls):
    if not hasattr(provider_cls, "matches"):
        pytest.skip("provider class predates matches() classmethod")
    assert provider_cls.matches(provider_cls.name)
    for alias in getattr(provider_cls, "aliases", ()):
        assert provider_cls.matches(alias), f"{provider_cls.__name__} should match alias '{alias}'"


# ── tool-schema converters ──────────────────────────────────────────────────

def _sample_tool():
    if compat.CalculatorTool is None:
        pytest.skip(compat.missing("CalculatorTool"))
    return compat.CalculatorTool()


def test_openai_schema_shape():
    if compat.tool_to_openai_schema is None:
        pytest.skip(compat.missing("tool_to_openai_schema"))
    schema = compat.tool_to_openai_schema(_sample_tool())
    assert schema["type"] == "function"
    assert schema["function"]["name"] == "calculator"
    assert "parameters" in schema["function"]


def test_anthropic_schema_shape():
    if compat.tool_to_anthropic_schema is None:
        pytest.skip(compat.missing("tool_to_anthropic_schema"))
    schema = compat.tool_to_anthropic_schema(_sample_tool())
    assert schema["name"] == "calculator"
    assert "input_schema" in schema  # Anthropic uses input_schema, not parameters


def test_google_declaration_shape():
    if compat.tool_to_google_declaration is None:
        pytest.skip(compat.missing("tool_to_google_declaration"))
    decl = compat.tool_to_google_declaration(_sample_tool())
    assert decl["name"] == "calculator"
    assert "parameters" in decl
