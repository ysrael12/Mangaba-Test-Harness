"""
Matrix execution + aggregated reporting.

Runs a suite once per plan target, emitting a JUnit XML per target (JUnit is
native to pytest — no extra dependency). The XMLs are parsed back into a compact
``provider × model`` table, and optionally dumped as JSON.
"""

from __future__ import annotations

import html
import json
import re
import tempfile
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from mangaba_test import compat, runner
from mangaba_test.plan import TestPlan


@dataclass
class ModuleCounts:
    """Per-module outcome counts within a single target run."""

    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: int = 0

    @property
    def total(self) -> int:
        return self.passed + self.failed + self.skipped + self.errors

    @property
    def ok(self) -> bool:
        return self.failed == 0 and self.errors == 0


@dataclass
class TargetResult:
    """Aggregated counts for one (provider, model) target."""

    target_id: str
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    errors: int = 0
    duration: float = 0.0
    exit_code: int = 0
    modules: Dict[str, ModuleCounts] = field(default_factory=dict)
    failures: List[str] = field(default_factory=list)

    @property
    def total(self) -> int:
        return self.passed + self.failed + self.skipped + self.errors

    @property
    def ok(self) -> bool:
        return self.failed == 0 and self.errors == 0


def _safe_name(target_id: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", target_id).strip("_")


def _module_of(testcase: ET.Element) -> str:
    """Derive a framework module name from a JUnit testcase element."""
    raw = testcase.get("file") or testcase.get("classname") or ""
    leaf = raw.replace("\\", "/").split("/")[-1]
    match = re.search(r"test_([A-Za-z0-9]+)", leaf)
    return match.group(1) if match else (leaf or "unknown")


def _outcome_of(testcase: ET.Element) -> str:
    """Classify a testcase as passed/failed/error/skipped."""
    for child in testcase:
        tag = child.tag.split("}")[-1]  # strip XML namespace if any
        if tag == "failure":
            return "failed"
        if tag == "error":
            return "error"
        if tag == "skipped":
            return "skipped"
    return "passed"


def _parse_junit(xml_path: Path, target_id: str, exit_code: int) -> TargetResult:
    """Parse per-testcase outcomes from a JUnit XML, grouped by module."""
    res = TargetResult(target_id=target_id, exit_code=exit_code)
    try:
        root = ET.parse(xml_path).getroot()
    except (ET.ParseError, FileNotFoundError, OSError):
        # No XML (e.g. collection error): reflect failure via exit code only.
        if exit_code != 0:
            res.errors = 1
        return res

    for tc in root.iter("testcase"):
        module = _module_of(tc)
        bucket = res.modules.setdefault(module, ModuleCounts())
        outcome = _outcome_of(tc)
        res.duration += float(tc.get("time", 0.0) or 0.0)
        if outcome == "passed":
            res.passed += 1
            bucket.passed += 1
        elif outcome == "failed":
            res.failed += 1
            bucket.failed += 1
            res.failures.append(f"{module}::{tc.get('name', '?')}")
        elif outcome == "error":
            res.errors += 1
            bucket.errors += 1
            res.failures.append(f"{module}::{tc.get('name', '?')} (error)")
        else:
            res.skipped += 1
            bucket.skipped += 1
    return res


def run_matrix(
    level: str,
    plan: TestPlan,
    *,
    markers: Optional[str] = None,
    keyword: Optional[str] = None,
    maxfail: Optional[int] = None,
    coverage: bool = False,
    report_dir: Optional[str] = None,
) -> Tuple[List[TargetResult], str]:
    """Run ``level`` suite for each target; return (results, report_dir)."""
    paths = runner.paths_for_suite(level)
    out_dir = report_dir or tempfile.mkdtemp(prefix="mth-report-")
    Path(out_dir).mkdir(parents=True, exist_ok=True)

    results: List[TargetResult] = []
    if not paths:
        return results, out_dir

    for target in plan.targets:
        sub = TestPlan(targets=[target], defaults=plan.defaults)
        xml_path = Path(out_dir) / f"{level}__{_safe_name(target.id)}.xml"
        spec = runner.RunSpec(
            paths=paths,
            markers=markers,
            keyword=keyword,
            maxfail=maxfail,
            coverage=coverage,
            extra=["--junitxml", str(xml_path)],
        )
        print(f"\n[mth] === {level} target {target.id} ===")
        code = runner.run(spec, plan=sub)
        results.append(_parse_junit(xml_path, target.id, code))

    return results, out_dir


def render_matrix(level: str, results: List[TargetResult]) -> str:
    """ASCII summary table: one row per target."""
    if not results:
        return f"[mth] no '{level}' suites present — nothing to aggregate"

    width = max((len(r.target_id) for r in results), default=10)
    width = max(width, len("target"))
    lines = [
        f"\n=== {level} matrix ===",
        f"  {'target':<{width}}  {'pass':>5} {'fail':>5} {'skip':>5} {'err':>4}  {'status':<6}",
        f"  {'-'*width}  {'-'*5:>5} {'-'*5:>5} {'-'*5:>5} {'-'*4:>4}  {'-'*6:<6}",
    ]
    for r in results:
        status = "OK" if r.ok else "FAIL"
        lines.append(
            f"  {r.target_id:<{width}}  {r.passed:>5} {r.failed:>5} "
            f"{r.skipped:>5} {r.errors:>4}  {status:<6}"
        )
    n_ok = sum(1 for r in results if r.ok)
    lines.append(f"\n  {n_ok}/{len(results)} targets OK")
    return "\n".join(lines)


def render_breakdown(results: List[TargetResult]) -> str:
    """Per-target, per-module text breakdown for the console."""
    if not results:
        return ""
    lines: List[str] = ["\n=== per-module breakdown ==="]
    for r in results:
        lines.append(f"  {r.target_id}")
        if not r.modules:
            lines.append("    (no module data)")
            continue
        for mod in sorted(r.modules):
            c = r.modules[mod]
            status = "OK" if c.ok else "FAIL"
            lines.append(
                f"    {mod:<16} pass={c.passed} fail={c.failed} "
                f"skip={c.skipped} err={c.errors}  [{status}]"
            )
        for fail in r.failures:
            lines.append(f"    ! {fail}")
    return "\n".join(lines)


def _cell_class(c: ModuleCounts) -> str:
    if c.failed or c.errors:
        return "fail"
    if c.total == 0 or c.passed == 0:
        return "skip"
    return "ok"


def write_html(level: str, results: List[TargetResult], out_dir: str) -> str:
    """Write a standalone HTML report: targets × modules matrix + details."""
    modules = sorted({m for r in results for m in r.modules})
    esc = html.escape

    head = (
        "<tr><th>target</th>"
        + "".join(f"<th>{esc(m)}</th>" for m in modules)
        + "<th>total</th><th>status</th></tr>"
    )

    rows = []
    for r in results:
        cells = []
        for m in modules:
            c = r.modules.get(m)
            if c is None:
                cells.append('<td class="na">-</td>')
            else:
                label = f"{c.passed}/{c.total}"
                cells.append(f'<td class="{_cell_class(c)}">{label}</td>')
        status = "OK" if r.ok else "FAIL"
        status_cls = "ok" if r.ok else "fail"
        cells.append(f"<td>{r.passed}/{r.total}</td>")
        cells.append(f'<td class="{status_cls}">{status}</td>')
        rows.append(f"<tr><th class='t'>{esc(r.target_id)}</th>{''.join(cells)}</tr>")

    details = []
    for r in results:
        if r.failures:
            items = "".join(f"<li>{esc(f)}</li>" for f in r.failures)
            details.append(f"<h3>{esc(r.target_id)}</h3><ul class='fails'>{items}</ul>")
    details_html = "".join(details) or "<p>No failures.</p>"

    n_ok = sum(1 for r in results if r.ok)
    doc = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8">
<title>MTH report — {esc(level)}</title>
<style>
 body{{font:14px/1.5 system-ui,sans-serif;margin:2rem;color:#1a1a1a}}
 h1{{font-size:1.3rem}} h2{{font-size:1.05rem;margin-top:2rem}}
 table{{border-collapse:collapse;margin-top:1rem}}
 th,td{{border:1px solid #ddd;padding:.35rem .6rem;text-align:center}}
 th.t,th[scope]{{text-align:left}} th.t{{text-align:left;font-weight:600}}
 .ok{{background:#e6f4ea;color:#137333}} .fail{{background:#fce8e6;color:#c5221f;font-weight:600}}
 .skip{{background:#fef7e0;color:#b06000}} .na{{color:#aaa}}
 ul.fails li{{color:#c5221f}} .meta{{color:#666;font-size:.85rem}}
</style></head><body>
<h1>Mangaba Test Harness — {esc(level)} matrix</h1>
<p class="meta">mangaba v{esc(compat.version or '?')} · generated {esc(datetime.now().isoformat(timespec='seconds'))} · {n_ok}/{len(results)} targets OK</p>
<table>{head}{''.join(rows)}</table>
<h2>Failures</h2>{details_html}
</body></html>"""

    path = Path(out_dir) / f"{level}__report.html"
    path.write_text(doc, encoding="utf-8")
    return str(path)


def write_json(level: str, results: List[TargetResult], out_dir: str) -> str:
    path = Path(out_dir) / f"{level}__matrix.json"
    payload = {"level": level, "targets": [asdict(r) for r in results]}
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return str(path)


def overall_exit_code(results: List[TargetResult]) -> int:
    return 0 if all(r.ok for r in results) else 1
