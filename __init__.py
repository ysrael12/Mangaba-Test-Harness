"""
Mangaba Test Harness (MTH)

Automated, modular test harness for the Mangaba AI agent framework.

Designed to be **version-resilient**: it never assumes a given symbol exists in
the installed ``mangaba`` package. Everything is resolved at runtime through
:mod:`mangaba_test.compat`, so the same suites run across multiple framework
versions — missing features are skipped, not errored.

See ``docs/SPEC-Test-Harness.md`` for the full specification.
"""

from __future__ import annotations

__version__ = "0.1.0"
__all__ = ["__version__"]
