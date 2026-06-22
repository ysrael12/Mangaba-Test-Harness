"""Unit — tools: calculator, decorator, JSON-schema generation (L1)."""

from __future__ import annotations

import pytest

from mangaba_test import compat

pytestmark = pytest.mark.unit


def test_calculator_tool():
    if compat.CalculatorTool is None:
        pytest.skip(compat.missing("CalculatorTool"))
    result = compat.CalculatorTool().run(expression="2 + 3")
    assert "5" in str(result)


def test_word_counter_tool():
    if compat.WordCounterTool is None:
        pytest.skip(compat.missing("WordCounterTool"))
    result = compat.WordCounterTool().run(text="hello world foo")
    assert "3" in str(result)


def test_tool_decorator():
    if compat.tool is None:
        pytest.skip(compat.missing("tool"))

    @compat.tool
    def add(a: int, b: int) -> str:
        """Add two numbers."""
        return str(a + b)

    assert add.name == "add"
    assert "Add two numbers." in add.description
    assert add.run(a=1, b=2) == "3"


def test_function_schema_shape():
    if compat.CalculatorTool is None:
        pytest.skip(compat.missing("CalculatorTool"))
    schema = compat.CalculatorTool().get_function_schema()
    assert schema["name"] == "calculator"
    assert "parameters" in schema
