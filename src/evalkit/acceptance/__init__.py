"""ACCEPTANCE — the 30 mandatory scenarios mapped to their covering tests, executed, reported.

The report is generated from test evidence (JUnit XML of a real pytest run), never written by
hand: a scenario is PASS only when every covering test passed in that run, BLOCKED when it
cannot run in this environment (the reason is printed), FAIL otherwise. Simulated agents are
labelled as such on every line.
"""

from evalkit.acceptance.registry import SCENARIOS, AcceptanceScenario, Mode
from evalkit.acceptance.report import (
    AcceptanceReport,
    ScenarioResult,
    build_report,
    parse_junit,
    render_markdown,
    run_acceptance,
)

__all__ = [
    "SCENARIOS",
    "AcceptanceReport",
    "AcceptanceScenario",
    "Mode",
    "ScenarioResult",
    "build_report",
    "parse_junit",
    "render_markdown",
    "run_acceptance",
]
