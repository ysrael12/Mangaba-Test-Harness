"""
``mth`` command-line interface.

Subcommands:
    doctor                 environment diagnostics (keys + SDKs)
    list-providers         providers known to the installed framework
    list-models            curated model catalogue (HuggingFace)
    run                    unit/module/iterative runs (offline by default)
    integration            module wiring across a provider×model matrix
    e2e                    real provider runs across the matrix

Selection of provider+model for LLM-touching runs is done via a plan file
(``--config plan.yaml``) or the ``--provider``/``--model`` shortcut.
"""

from __future__ import annotations

import argparse
import sys
from typing import List, Optional

from mangaba_test import __version__, compat
from mangaba_test import doctor as doctor_mod
from mangaba_test import reporting
from mangaba_test import runner
from mangaba_test.plan import TestPlan


def _add_target_flags(p: argparse.ArgumentParser) -> None:
    p.add_argument("--config", help="path to a plan file (.yaml/.yml/.json)")
    p.add_argument("--provider", help="provider name (shortcut, no config file)")
    p.add_argument("--model", help="model id, or comma list = OpenRouter fallback")
    p.add_argument("--api-key-env", help="env var holding the API key")
    p.add_argument("--temperature", type=float, default=0.0)
    p.add_argument("--max-output-tokens", type=int, default=512)
    p.add_argument("--timeout", type=int, default=60)


def _add_select_flags(p: argparse.ArgumentParser) -> None:
    p.add_argument("-k", dest="keyword", help="pytest -k expression")
    p.add_argument("-m", dest="markers", help="pytest -m marker expression")
    p.add_argument("--maxfail", type=int)
    p.add_argument("--cov", action="store_true", help="enable coverage reporting")


def _add_report_flags(p: argparse.ArgumentParser) -> None:
    p.add_argument("--report", dest="report_dir", help="directory for JUnit XML + JSON/HTML artifacts")
    p.add_argument("--format", dest="report_format", choices=["table", "json", "html"], default="table")
    p.add_argument("--breakdown", action="store_true", help="print per-module breakdown to the console")


def _plan_from_args(args: argparse.Namespace) -> Optional[TestPlan]:
    if getattr(args, "config", None):
        plan = TestPlan.from_file(args.config)
    elif getattr(args, "provider", None):
        model: object = args.model or "mock-model"
        if isinstance(model, str) and "," in model:
            model = [m.strip() for m in model.split(",")]
        plan = TestPlan.single(
            args.provider, model, api_key_env=getattr(args, "api_key_env", None),
        )
    else:
        return None

    plan.defaults.setdefault("temperature", args.temperature)
    plan.defaults.setdefault("max_output_tokens", args.max_output_tokens)
    plan.defaults.setdefault("timeout", args.timeout)
    for t in plan.targets:
        for k, v in plan.defaults.items():
            t.options.setdefault(k, v)

    problems = plan.validate()
    if problems:
        for p in problems:
            print(f"[mth] plan error: {p}", file=sys.stderr)
        sys.exit(2)
    return plan


# ── command handlers ────────────────────────────────────────────────────────

def cmd_doctor(args: argparse.Namespace) -> int:
    print(doctor_mod.render())
    return 0


def cmd_list_providers(args: argparse.Namespace) -> int:
    if compat.get_supported_providers is None:
        print("[mth] framework does not expose get_supported_providers()", file=sys.stderr)
        return 1
    for name in compat.get_supported_providers():
        print(name)
    print("mock  (harness-provided)")
    return 0


def cmd_list_models(args: argparse.Namespace) -> int:
    if compat.list_huggingface_models is None:
        print("[mth] framework does not expose a model catalogue", file=sys.stderr)
        return 1
    models = compat.list_huggingface_models(args.category)
    for m in models:
        tools = "tools" if m.get("tool_calling") else "no-tools"
        print(f"{m['id']:<48}{m.get('category',''):<12}{tools}")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
    plan = _plan_from_args(args)
    if args.iterative:
        return runner.run_iterative(plan, keyword=args.keyword, coverage=args.cov)
    if args.module:
        paths = runner.paths_for_module(args.module)
    elif args.modules:
        paths = runner.paths_for_modules([m.strip() for m in args.modules.split(",")])
    elif args.suite:
        paths = runner.paths_for_suite(args.suite)
    else:
        paths = runner.paths_for_suite("unit")
    spec = runner.RunSpec(
        paths=paths, markers=args.markers, keyword=args.keyword,
        maxfail=args.maxfail, coverage=args.cov,
    )
    return runner.run(spec, plan=plan)


def _matrix_run(args: argparse.Namespace, level: str) -> int:
    plan = _plan_from_args(args)
    if plan is None:
        print(f"[mth] {level} needs a plan: pass --config or --provider/--model", file=sys.stderr)
        return 2
    results, out_dir = reporting.run_matrix(
        level, plan,
        markers=args.markers, keyword=args.keyword,
        maxfail=args.maxfail, coverage=args.cov,
        report_dir=getattr(args, "report_dir", None),
    )
    if not results:
        print(f"[mth] no '{level}' suites present yet")
        return 0

    print(reporting.render_matrix(level, results))

    fmt = getattr(args, "report_format", "table")
    if getattr(args, "breakdown", False) or fmt in ("json", "html"):
        print(reporting.render_breakdown(results))

    artifacts: list[str] = []
    persist = bool(getattr(args, "report_dir", None))
    if fmt == "json" or persist:
        artifacts.append(reporting.write_json(level, results, out_dir))
    if fmt == "html" or persist:
        artifacts.append(reporting.write_html(level, results, out_dir))
    if artifacts:
        print(f"\n[mth] artifacts in {out_dir}")
        for path in artifacts:
            print(f"[mth]   {path}")
    return reporting.overall_exit_code(results)


def cmd_integration(args: argparse.Namespace) -> int:
    return _matrix_run(args, "integration")


def cmd_e2e(args: argparse.Namespace) -> int:
    return _matrix_run(args, "e2e")


# ── parser ──────────────────────────────────────────────────────────────────

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="mth", description="Mangaba Test Harness")
    parser.add_argument("--version", action="version", version=f"mth {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("doctor", help="environment diagnostics").set_defaults(func=cmd_doctor)
    sub.add_parser("list-providers", help="list known providers").set_defaults(func=cmd_list_providers)

    lm = sub.add_parser("list-models", help="list catalogued models")
    lm.add_argument("--provider", default="huggingface")
    lm.add_argument("--category", choices=["general", "code", "reasoning", "embedding"])
    lm.set_defaults(func=cmd_list_models)

    r = sub.add_parser("run", help="run unit/module/iterative suites (offline)")
    r.add_argument("--module", help="single module suite (e.g. tools)")
    r.add_argument("--modules", help="comma-separated module list")
    r.add_argument("--suite", choices=["unit", "contract", "integration", "e2e"])
    r.add_argument("--iterative", action="store_true", help="run layers L0→L6, stop on first failure")
    _add_select_flags(r)
    _add_target_flags(r)
    r.set_defaults(func=cmd_run)

    integ = sub.add_parser("integration", help="module wiring across provider×model matrix")
    _add_select_flags(integ)
    _add_report_flags(integ)
    _add_target_flags(integ)
    integ.set_defaults(func=cmd_integration)

    e2e = sub.add_parser("e2e", help="real provider runs across provider×model matrix")
    _add_select_flags(e2e)
    _add_report_flags(e2e)
    _add_target_flags(e2e)
    e2e.set_defaults(func=cmd_e2e)

    return parser


def main(argv: Optional[List[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
