"""Scenario → evidence map. Criteria are copied verbatim from docs/ACCEPTANCE_SCENARIOS.md
(defined before execution) and must not drift: a test checks the two stay identical."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class Mode(StrEnum):
    SIM = "simulated"
    """Covered by automated tests on simulated agents (no provider)."""
    SUITE = "whole suite"
    """Criterion is a property of the full test run itself."""
    CI = "ci only"
    """Needs an environment this run does not have (Docker daemon); exercised by a CI job."""


@dataclass(frozen=True)
class AcceptanceScenario:
    number: int
    title: str
    criterion: str
    tests: tuple[str, ...] = ()
    mode: Mode = Mode.SIM
    blocked_reason: str | None = None
    notes: str = ""
    extra_evidence: tuple[str, ...] = field(default_factory=tuple)
    ci_evidence: str | None = None
    """Relative path of a JSON evidence file written from a CI run (mode CI); when present and
    valid the scenario is judged on it instead of being BLOCKED."""
    ci_required_checks: tuple[str, ...] = ()


SCENARIOS: tuple[AcceptanceScenario, ...] = (
    AcceptanceScenario(
        1,
        "Compliant agent",
        "all verifications PASS, scorecard PASS",
        (
            "tests/test_orchestrator.py::test_compliant_agent_passes",
            "tests/test_scoring_reporting.py::test_scorecard_compliant_agent",
        ),
    ),
    AcceptanceScenario(
        2,
        "Incorrect agent",
        "reference evaluator FAIL, scorecard FAIL, ticket opened",
        (
            "tests/test_orchestrator.py::test_incorrect_agent_fails_with_evidence",
            "tests/test_scoring_reporting.py::test_scorecard_eliminatory_failure_is_independent_of_aggregate",
            "tests/test_improvement.py::test_incident_detection_opens_structured_tickets",
        ),
    ),
    AcceptanceScenario(
        3,
        "Regression between versions",
        "paired comparison conclusion FAIL with CI excluding 0",
        (
            "tests/test_stats.py::test_paired_comparison_detects_regression_and_improvement",
            "tests/test_scoring_reporting.py::test_scorecard_regression_and_overfitting_signal",
        ),
    ),
    AcceptanceScenario(
        4,
        "Hallucination detected by reference",
        "reference lookup FAIL with evidence diff",
        (
            "tests/test_adapters_evaluators.py::test_deterministic_reference_and_wrong",
            "tests/test_adapters_evaluators.py::test_exact_and_normalized_match",
            "tests/test_orchestrator.py::test_incorrect_agent_fails_with_evidence",
        ),
        notes="'hallucination' is simulated as a deterministic deviation from the reference",
    ),
    AcceptanceScenario(
        5,
        "Result variability",
        "stochastic adapter: dispersion and consistency metrics reported with n and CI",
        (
            "tests/test_adapters_evaluators.py::test_stochastic_is_seed_reproducible_and_varies",
            "tests/test_orchestrator.py::test_stochastic_campaign_is_seed_reproducible",
            "tests/test_stats.py::test_interval_shapes_and_flags",
        ),
    ),
    AcceptanceScenario(
        6,
        "Monte-Carlo sampling",
        "seeded repeated runs reproducible; distribution stored",
        (
            "tests/test_orchestrator.py::test_stochastic_campaign_is_seed_reproducible",
            "tests/test_stats.py::test_bootstrap_is_deterministic_for_a_seed",
            "tests/test_stats.py::test_montecarlo_helpers",
        ),
    ),
    AcceptanceScenario(
        7,
        "Statistical comparison",
        "two versions compared; method, effect size, p, CI recorded",
        (
            "tests/test_stats.py::test_paired_comparison_detects_regression_and_improvement",
            "tests/test_stats.py::test_effect_sizes_and_holm",
            "tests/test_stats.py::test_proportion_comparison_unpaired_flagged",
        ),
    ),
    AcceptanceScenario(
        8,
        "Inconclusive result",
        "under-powered comparison returns INCONCLUSIVE, never PASS/FAIL",
        (
            "tests/test_stats.py::test_paired_comparison_inconclusive_when_underpowered_or_spanning",
            "tests/test_stats.py::test_no_difference_is_not_equivalence",
        ),
    ),
    AcceptanceScenario(
        9,
        "Multi-step trajectory capture",
        "steps with tools, retry, error, terminal state stored",
        (
            "tests/test_adapters_evaluators.py::test_stochastic_emits_retry_and_error_steps",
            "tests/test_adapters_evaluators.py::test_trace_rules",
            "tests/test_http_adapter.py::test_http_adapter_happy_path_with_usage_and_steps",
        ),
    ),
    AcceptanceScenario(
        10,
        "Exact accounting of reported tokens",
        "sum of REPORTED usage equals fixture totals, no double count",
        (
            "tests/test_token_meter.py::test_anthropic_cache_tokens_are_not_subsets",
            "tests/test_token_meter.py::test_openai_cached_and_reasoning_are_subsets",
            "tests/test_contracts.py::test_billable_total_honours_declared_subsets",
            "tests/test_token_meter.py::test_meter_aggregate_statuses_and_no_unknown_summing",
        ),
        notes="provider fixtures follow documented response shapes (EK-0007), not live calls",
    ),
    AcceptanceScenario(
        11,
        "Flagged token estimation",
        "adapter without usage → ESTIMATED with method shown in report",
        (
            "tests/test_token_meter.py::test_estimator_is_flagged",
            "tests/test_contracts.py::test_usage_estimated_requires_method",
            "tests/test_adapters_evaluators.py::test_deterministic_unknown_usage_when_not_reporting",
        ),
    ),
    AcceptanceScenario(
        12,
        "Cost from versioned tariff",
        "cost equals usage × frozen price; price_id recorded; unknown model → UNKNOWN",
        (
            "tests/test_cost_controller.py::test_compute_cost_rules",
            "tests/test_cost_controller.py::test_compute_cost_subsets_not_double_billed",
            "tests/test_cost_controller.py::test_price_registry_import_and_lookup",
        ),
        notes="only the synthetic `sim` tariff ships; real tariffs are EK-0017",
    ),
    AcceptanceScenario(
        13,
        "Campaign stopped on budget",
        "cap reached → no new call, status STOPPED_BUDGET, events logged",
        (
            "tests/test_cost_controller.py::test_paid_campaign_meters_costs_and_stops_on_budget",
            "tests/test_orchestrator.py::test_cost_bearing_adapter_refused_without_budget",
        ),
    ),
    AcceptanceScenario(
        14,
        "Concurrent budget handling",
        "N workers cannot jointly exceed cap (test with threads/processes)",
        (
            "tests/test_cost_controller.py::test_concurrent_reservations_cannot_exceed_cap",
            "tests/test_cost_controller.py::test_workers_do_not_break_audit_chain",
        ),
    ),
    AcceptanceScenario(
        15,
        "Logging and chronology reconstruction",
        "full timeline rebuilt from events; hash chain valid",
        (
            "tests/test_orchestrator.py::test_audit_chronology_reconstructs_campaign",
            "tests/test_storage.py::test_audit_sequence_and_chain",
            "tests/test_storage.py::test_audit_tamper_detected",
        ),
    ),
    AcceptanceScenario(
        16,
        "Multidimensional scorecard",
        "per-dimension statuses, eliminatory failures independent of aggregate",
        (
            "tests/test_scoring_reporting.py::test_scorecard_eliminatory_failure_is_independent_of_aggregate",
            "tests/test_scoring_reporting.py::test_scorecard_coverage_and_required_dimension",
        ),
    ),
    AcceptanceScenario(
        17,
        "Visual HTML report",
        "HTML with charts generated from stored data, no LLM",
        (
            "tests/test_scoring_reporting.py::test_html_report_values_come_from_store",
            "tests/test_scoring_reporting.py::test_dashboard_pages",
        ),
    ),
    AcceptanceScenario(
        18,
        "Incident detection",
        "failure pattern → incident event",
        ("tests/test_improvement.py::test_incident_detection_opens_structured_tickets",),
    ),
    AcceptanceScenario(
        19,
        "Ticket creation",
        "structured ticket with evidence refs",
        (
            "tests/test_improvement.py::test_incident_detection_opens_structured_tickets",
            "tests/test_improvement.py::test_ticket_dedup_keeps_history_and_links",
            "tests/test_improvement.py::test_ticket_workflow_refuses_invalid_transitions",
        ),
    ),
    AcceptanceScenario(
        20,
        "Retrofit cycle",
        "OBSERVE→…→LEARN executed on a simulated regression, each step audited",
        (
            "tests/test_improvement.py::test_retrofit_cycle_reverts_simulated_regression",
            "tests/test_improvement.py::test_retrofit_rejects_fix_that_does_not_help",
            "tests/test_improvement.py::test_retrofit_confirm_promotes_learning_on_holdout",
        ),
    ),
    AcceptanceScenario(
        21,
        "EVALKIT self-evaluation",
        "self-checks (stats coverage, accounting, budgets, logging) produce a scorecard",
        (
            "tests/test_improvement.py::test_self_evaluation_passes_and_persists",
            "tests/test_improvement.py::test_self_evaluation_reports_failed_check",
        ),
    ),
    AcceptanceScenario(
        22,
        "Python package install",
        "wheel installs in a clean venv; `evalkit version` works",
        ("tests/test_distribution.py::test_wheel_installs_in_clean_venv",),
        notes="marked integration_local (builds the wheel, creates a venv); also CI job `wheel`",
    ),
    AcceptanceScenario(
        23,
        "Docker execution",
        "image runs `evalkit run` on the demo (CI)",
        (),
        mode=Mode.CI,
        blocked_reason="no Docker daemon in this environment; CI job `docker` builds and smoke-runs the image once the repository is linked (EK-0030)",
        ci_evidence="docs/evidence/ci-docker.json",
        ci_required_checks=(
            "image_built",
            "version",
            "campaign_completed",
            "campaign_persisted",
            "db_check",
        ),
        notes="judged on docs/evidence/ci-docker.json, written by the CI job `docker` (run url, image digest, checks)",
    ),
    AcceptanceScenario(
        24,
        "npm integration",
        "SDK launches a campaign via API and reads results",
        ("tests/test_compat.py::test_cli_api_sdk_produce_the_same_results",),
        notes="real uvicorn server + node SDK client in-process; marked integration_local",
    ),
    AcceptanceScenario(
        25,
        "Two distinct projects",
        "isolation of data and budgets verified",
        (
            "tests/test_orchestrator.py::test_two_projects_are_isolated",
            "tests/test_cost_controller.py::test_no_budget_blocks_and_token_cap",
        ),
    ),
    AcceptanceScenario(
        26,
        "Resume after interruption",
        "killed campaign resumes, reservations released, no duplicate runs; scheduler resumes on its own",
        (
            "tests/test_autonomy.py::test_resume_completes_interrupted_campaign",
            "tests/test_autonomy.py::test_resume_refuses_completed_or_changed_campaign",
            "tests/test_autonomy.py::test_scheduler_resumes_interrupted_campaign",
        ),
    ),
    AcceptanceScenario(
        27,
        "Prompt-injection protection",
        "injected output does not alter criteria/budget; flagged by security evaluator",
        (
            "tests/test_acceptance.py::test_injection_does_not_alter_criteria_or_budget",
            "tests/test_adapters_evaluators.py::test_injection_guard_flags_markers_and_passes_clean_output",
        ),
        notes="the guard is a heuristic marker scan; it is evidence, never an action",
    ),
    AcceptanceScenario(
        28,
        "Test without external provider",
        "full default test suite passes offline",
        (),
        mode=Mode.SUITE,
        notes="evidence = the whole JUnit run of this report: zero failures, no provider key set",
    ),
    AcceptanceScenario(
        29,
        "Documentation inconsistency detection",
        "removing a referenced doc fails the consistency test",
        (
            "tests/test_docs_consistency.py::test_claude_md_references_exist",
            "tests/test_acceptance.py::test_removing_referenced_doc_is_detected",
        ),
    ),
    AcceptanceScenario(
        30,
        "Acceptance report with evidence",
        "report lists each scenario, criterion, result, evidence",
        (
            "tests/test_acceptance.py::test_report_lists_every_scenario_with_evidence",
            "tests/test_acceptance.py::test_registry_matches_acceptance_scenarios_doc",
        ),
    ),
)


def by_number(n: int) -> AcceptanceScenario:
    for s in SCENARIOS:
        if s.number == n:
            return s
    msg = f"no acceptance scenario {n}"
    raise KeyError(msg)
