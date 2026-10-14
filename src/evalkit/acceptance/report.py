"""Run the suite, read the JUnit evidence, decide each scenario, render the report."""

from __future__ import annotations

import os
import platform
import subprocess
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path

from evalkit import __version__
from evalkit.acceptance.registry import SCENARIOS, AcceptanceScenario, Mode
from evalkit.contracts import utcnow

PROVIDER_KEYS = ("ANTHROPIC_API_KEY", "OPENAI_API_KEY")


@dataclass
class TestOutcome:
    nodeid: str
    outcome: str
    """passed | failed | error | skipped"""
    duration_s: float
    message: str = ""


@dataclass
class ScenarioResult:
    scenario: AcceptanceScenario
    result: str
    """PASS | FAIL | BLOCKED | NOT_RUN"""
    evidence: list[TestOutcome] = field(default_factory=list)
    detail: str = ""


@dataclass
class AcceptanceReport:
    generated_at: str
    evalkit_version: str
    git_commit: str | None
    python: str
    platform: str
    provider_keys_present: list[str]
    junit_path: str
    total_tests: int
    passed: int
    failed: int
    errors: int
    skipped: int
    results: list[ScenarioResult]

    @property
    def counts(self) -> dict[str, int]:
        c = {"PASS": 0, "FAIL": 0, "BLOCKED": 0, "NOT_RUN": 0}
        for r in self.results:
            c[r.result] += 1
        return c

    @property
    def accepted(self) -> bool:
        return self.counts["FAIL"] == 0 and self.counts["NOT_RUN"] == 0


def _nodeid(testcase: ET.Element) -> str:
    classname = testcase.get("classname", "")
    name = testcase.get("name", "")
    # pytest: classname "tests.test_x" (+ ".Class") → "tests/test_x.py::name"
    parts = classname.split(".")
    file_parts: list[str] = []
    cls_parts: list[str] = []
    for p in parts:
        (
            cls_parts
            if file_parts and file_parts[-1].startswith("test_") and p[:1].isupper()
            else file_parts
        ).append(p)
    path = "/".join(file_parts) + ".py"
    base = name.split("[", 1)[0]
    return "::".join([path, *cls_parts, base])


def parse_junit(path: Path) -> dict[str, TestOutcome]:
    """Map base node ids (parametrized ids collapsed, worst outcome kept) → outcome."""
    root = ET.parse(path).getroot()  # noqa: S314 — JUnit written by our own pytest run
    rank = {"passed": 0, "skipped": 1, "failed": 2, "error": 3}
    out: dict[str, TestOutcome] = {}
    for tc in root.iter("testcase"):
        nodeid = _nodeid(tc)
        outcome, message = "passed", ""
        for child in tc:
            if child.tag in ("failure", "error", "skipped"):
                outcome = {"failure": "failed", "error": "error", "skipped": "skipped"}[child.tag]
                message = (child.get("message") or "")[:300]
        duration = float(tc.get("time", "0") or 0)
        prev = out.get(nodeid)
        if prev is None:
            out[nodeid] = TestOutcome(nodeid, outcome, duration, message)
        else:
            prev.duration_s += duration
            if rank[outcome] > rank[prev.outcome]:
                prev.outcome, prev.message = outcome, message
    return out


def _git(root: Path, *args: str) -> str:
    return subprocess.run(
        ["git", *args], cwd=root, capture_output=True, text=True, check=True, timeout=10
    ).stdout.strip()


def _git_commit(root: Path) -> str | None:
    """Short HEAD, suffixed ``+dirty`` when the working tree differs from it."""
    try:
        head = _git(root, "rev-parse", "--short", "HEAD")
        return (head + ("+dirty" if _git(root, "status", "--porcelain") else "")) or None
    except (OSError, subprocess.SubprocessError):
        return None


def build_report(
    outcomes: dict[str, TestOutcome], *, junit_path: Path, root: Path
) -> AcceptanceReport:
    total = len(outcomes)
    failed = sum(1 for o in outcomes.values() if o.outcome == "failed")
    errors = sum(1 for o in outcomes.values() if o.outcome == "error")
    skipped = sum(1 for o in outcomes.values() if o.outcome == "skipped")
    passed = total - failed - errors - skipped
    results: list[ScenarioResult] = []
    for sc in SCENARIOS:
        if sc.mode is Mode.CI:
            results.append(ScenarioResult(sc, "BLOCKED", [], sc.blocked_reason or "blocked"))
            continue
        if sc.mode is Mode.SUITE:
            ok = failed == 0 and errors == 0 and total > 0
            keys = [k for k in PROVIDER_KEYS if os.environ.get(k)]
            detail = f"{passed} passed, {failed} failed, {errors} errors, {skipped} skipped; provider keys set: {keys or 'none'}"
            results.append(ScenarioResult(sc, "PASS" if ok and not keys else "FAIL", [], detail))
            continue
        ev = [
            outcomes.get(t) or TestOutcome(t, "not_run", 0.0, "not in this run") for t in sc.tests
        ]
        if any(o.outcome == "not_run" for o in ev):
            res, detail = "NOT_RUN", "a covering test was not executed in this run"
        elif all(o.outcome == "passed" for o in ev):
            res, detail = "PASS", f"{len(ev)} covering test(s) passed"
        elif any(o.outcome in ("failed", "error") for o in ev):
            res, detail = (
                "FAIL",
                "; ".join(f"{o.nodeid}: {o.message}" for o in ev if o.outcome != "passed"),
            )
        else:
            res, detail = "NOT_RUN", "a covering test was skipped"
        results.append(ScenarioResult(sc, res, ev, detail))
    return AcceptanceReport(
        generated_at=utcnow().isoformat(timespec="seconds"),
        evalkit_version=__version__,
        git_commit=_git_commit(root),
        python=platform.python_version(),
        platform=platform.platform(),
        provider_keys_present=[k for k in PROVIDER_KEYS if os.environ.get(k)],
        junit_path=str(junit_path),
        total_tests=total,
        passed=passed,
        failed=failed,
        errors=errors,
        skipped=skipped,
        results=results,
    )


def render_markdown(report: AcceptanceReport) -> str:
    c = report.counts
    verdict = (
        "**ACCEPTED** — every executable scenario passed; blocked scenarios are listed with their reason"
        if report.accepted
        else "**NOT ACCEPTED** — see FAIL / NOT_RUN lines"
    )
    lines = [
        "# Acceptance report",
        "",
        "Generated by `evalkit acceptance run` from a real test execution — never edited by hand.",
        "Criteria were defined before execution (`docs/ACCEPTANCE_SCENARIOS.md`). Every covering",
        "test runs on **simulated agents**: this report validates EVALKIT's mechanisms, not any",
        "production agent.",
        "",
        f"- Generated: {report.generated_at}",
        f"- EVALKIT {report.evalkit_version}, commit `{report.git_commit or 'n/a'}`, Python {report.python}, {report.platform}",
        f"- Provider keys present: {', '.join(report.provider_keys_present) or 'none (offline run)'}",
        f"- Test run: {report.total_tests} test functions (parametrized cases collapsed) — {report.passed} passed, {report.failed} failed, {report.errors} errors, {report.skipped} skipped (`{report.junit_path}`)",
        f"- Scenarios: {c['PASS']} PASS, {c['FAIL']} FAIL, {c['BLOCKED']} BLOCKED, {c['NOT_RUN']} NOT_RUN",
        "",
        f"Verdict: {verdict}.",
        "",
        "| # | Scenario | Result | Mode | Criterion | Evidence |",
        "|---|---|---|---|---|---|",
    ]
    for r in report.results:
        sc = r.scenario
        ev = (
            "<br>".join(f"`{o.nodeid}` {o.outcome} ({o.duration_s:.2f}s)" for o in r.evidence)
            or r.detail
        )
        lines.append(
            f"| {sc.number} | {sc.title} | **{r.result}** | {sc.mode.value} | {sc.criterion} | {ev} |"
        )
    lines += ["", "## Details", ""]
    for r in report.results:
        sc = r.scenario
        lines.append(f"### {sc.number}. {sc.title} — {r.result}")
        lines.append("")
        lines.append(f"- Criterion: {sc.criterion}")
        lines.append(f"- Mode: {sc.mode.value}")
        if sc.notes:
            lines.append(f"- Note: {sc.notes}")
        if r.detail:
            lines.append(f"- Detail: {r.detail}")
        for o in r.evidence:
            msg = f" — {o.message}" if o.message else ""
            lines.append(f"- `{o.nodeid}`: {o.outcome} in {o.duration_s:.2f}s{msg}")
        lines.append("")
    return "\n".join(lines)


def run_acceptance(
    root: Path,
    *,
    out: Path | None,
    junit: Path | None = None,
    pytest_args: list[str] | None = None,
    python: str | None = None,
) -> AcceptanceReport:
    """Execute the whole suite (including integration_local tests) with JUnit output."""
    junit = junit or (root / "data" / "acceptance" / f"junit-{utcnow():%Y%m%dT%H%M%S}.xml")
    junit.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        python or sys.executable,
        "-m",
        "pytest",
        "-o",
        "addopts=",
        "-q",
        "-p",
        "no:cacheprovider",
        f"--junitxml={junit}",
        *(pytest_args or []),
    ]
    subprocess.run(cmd, cwd=root, check=False, timeout=3600)  # failures are reported, not raised
    report = build_report(parse_junit(junit), junit_path=junit, root=root)
    if out is not None:
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(render_markdown(report), encoding="utf-8")
    return report
