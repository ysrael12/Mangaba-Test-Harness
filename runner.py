"""
Execution orchestration over pytest.

The harness does not reinvent a test runner — it drives the project's existing
pytest in a subprocess, neutralising the repo's coverage ``addopts`` (which force
``--cov-fail-under=80`` and would fail partial runs) and injecting selection by
module, suite level, or dependency layer.

Layers mirror the real import DAG of the framework (see SPEC §2.1); ``iterative``
mode runs them L0→L6 and stops at the first failing layer.
"""

from __future__ import annotations

import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from mangaba_test.plan import TestPlan

SUITES_DIR = Path(__file__).parent / "suites"

# Suite levels → subdirectory under suites/.
SUITE_LEVELS = {
    "unit": SUITES_DIR / "unit",
    "contract": SUITES_DIR / "contract",
    "integration": SUITES_DIR / "integration",
    "e2e": SUITES_DIR / "e2e",
}

# Module → test file(s). Used by ``run --module <name>``.
MODULE_SUITES: Dict[str, List[str]] = {
    "types": ["unit/test_types.py"],
    "events": ["unit/test_events.py"],
    "tools": ["unit/test_tools.py"],
    "guardrails": ["unit/test_guardrails.py"],
    "output_parsers": ["unit/test_output_parsers.py"],
    "memory": ["unit/test_memory.py"],
    "vectorstores": ["unit/test_vectorstores.py"],
    "protocols": ["unit/test_protocols.py"],
    "assertions": ["unit/test_assertions.py"],
    "llm": ["contract/test_llm_contract.py", "contract/test_provider_matrix.py"],
    "reasoning": ["integration/test_reasoning.py"],
    "agent": ["integration/test_agent.py"],
    "crew": ["integration/test_crew.py"],
}

# Dependency layers (SPEC §2.1) → modules. Order matters for iterative mode.
LAYERS: List[tuple[str, List[str]]] = [
    ("L0-foundation", ["types", "events"]),
    ("L1-primitives", ["tools", "guardrails", "output_parsers", "memory", "vectorstores", "protocols", "assertions"]),
    ("L2-providers", ["llm"]),
    ("L3-reasoning", ["reasoning"]),
    ("L4-agent", ["agent"]),
    ("L6-orchestration", ["crew"]),
]


@dataclass
class RunSpec:
    """Resolved description of what pytest should execute."""

    paths: List[str]
    markers: Optional[str] = None
    keyword: Optional[str] = None
    maxfail: Optional[int] = None
    coverage: bool = False
    extra: Optional[List[str]] = None


def _existing(rel_paths: List[str]) -> List[str]:
    """Filter to test files that actually exist (tolerates not-yet-written suites)."""
    out: List[str] = []
    for rel in rel_paths:
        p = SUITES_DIR / rel
        if p.exists():
            out.append(str(p))
    return out


def paths_for_module(module: str) -> List[str]:
    return _existing(MODULE_SUITES.get(module, []))


def paths_for_modules(modules: List[str]) -> List[str]:
    paths: List[str] = []
    for m in modules:
        paths.extend(MODULE_SUITES.get(m, []))
    return _existing(paths)


def paths_for_suite(level: str) -> List[str]:
    d = SUITE_LEVELS.get(level)
    return [str(d)] if d and d.exists() else []


def build_pytest_argv(spec: RunSpec) -> List[str]:
    """Assemble the pytest argv, clearing repo addopts to avoid forced coverage."""
    argv = [sys.executable, "-m", "pytest"]
    # Neutralise the repository's forced coverage/strict addopts.
    argv += ["-o", "addopts=", "-p", "no:cacheprovider"]
    if not spec.coverage:
        argv += ["-p", "no:cov"]
    argv += ["--no-header", "-ra"]
    if spec.markers:
        argv += ["-m", spec.markers]
    if spec.keyword:
        argv += ["-k", spec.keyword]
    if spec.maxfail is not None:
        argv += [f"--maxfail={spec.maxfail}"]
    if spec.extra:
        argv += spec.extra
    argv += spec.paths
    return argv


def run(spec: RunSpec, plan: Optional[TestPlan] = None) -> int:
    """Run a single pytest invocation; returns its exit code."""
    if not spec.paths:
        print("[mth] nothing to run (no matching test files found)")
        return 0
    if plan is not None:
        plan.export_env()
    argv = build_pytest_argv(spec)
    print(f"[mth] $ {' '.join(argv)}")
    return subprocess.call(argv)


def run_iterative(
    plan: Optional[TestPlan] = None,
    *,
    keyword: Optional[str] = None,
    coverage: bool = False,
) -> int:
    """Run layers L0→L6, short-circuiting at the first failing layer."""
    for layer_name, modules in LAYERS:
        paths = paths_for_modules(modules)
        if not paths:
            print(f"[mth] {layer_name}: no suites present, skipping")
            continue
        print(f"\n[mth] === layer {layer_name} ({', '.join(modules)}) ===")
        code = run(
            RunSpec(paths=paths, keyword=keyword, coverage=coverage),
            plan=plan,
        )
        if code != 0:
            print(f"\n[mth] STOP — layer {layer_name} failed (exit {code}). "
                  f"Fix this layer before higher layers can be trusted.")
            return code
    print("\n[mth] all layers passed [OK]")
    return 0
