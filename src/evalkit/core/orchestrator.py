"""Campaign orchestrator: scenario → run → evaluation → audit, persisted step by step.

Phase 2 scope: sequential execution, profiles QUICK/STANDARD/DEEP/EXTENDED with explicit V1
rules, DRY_RUN, eliminatory early-stop (opt-in). Budget reservation arrives in Phase 3: until
then any *cost-bearing* adapter is refused outright (never silently run unmetered).
"""

from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from evalkit import __version__
from evalkit.adapters import AgentAdapter, create_adapter
from evalkit.audit import make_event
from evalkit.contracts import (
    Campaign,
    CampaignPlan,
    CampaignStatus,
    ControlState,
    Criticality,
    DatasetKind,
    EvalStatus,
    EvaluationResult,
    EventType,
    MeasurementKind,
    Profile,
    Run,
    RunStatus,
    Scenario,
    Severity,
    Trajectory,
    TrajectoryStep,
    new_id,
    utcnow,
)
from evalkit.core.project import ProjectConfig, load_project, load_scenarios
from evalkit.evaluators import DefaultEvaluatorRegistry, EvaluatorRegistry
from evalkit.storage.sqlite import SQLiteRepository

DEFAULT_TIMEOUT_S = 60.0


class CampaignRefusedError(RuntimeError):
    """Raised before any run when governance or cost rules forbid the campaign."""


@dataclass
class PlannedCampaign:
    campaign: Campaign
    config: ProjectConfig
    scenarios: list[Scenario]
    repetitions: dict[str, int]
    adapter: AgentAdapter
    rules: list[str] = field(default_factory=list)

    @property
    def planned_runs(self) -> int:
        return sum(self.repetitions.values())


def _select(
    scenarios: list[Scenario], profile: Profile, deterministic: bool, override: int | None
) -> tuple[list[Scenario], dict[str, int], list[str]]:
    """V1 profile rules (docs/EVALUATION_PROTOCOL.md §4). Explicit and recorded."""
    rules: list[str] = []
    if profile is Profile.QUICK:
        chosen = [s for s in scenarios if s.criticality in (Criticality.CRITICAL, Criticality.HIGH)]
        chosen = [s for s in chosen if s.dataset is DatasetKind.DEVELOPMENT]
        rules.append("QUICK: CRITICAL/HIGH scenarios only, DEVELOPMENT set, 1 repetition")
        reps = dict.fromkeys((s.scenario_id for s in chosen), 1)
    elif profile is Profile.STANDARD:
        chosen = [s for s in scenarios if s.dataset is DatasetKind.DEVELOPMENT]
        rules.append("STANDARD: all DEVELOPMENT scenarios, repetitions from scenario")
        reps = {s.scenario_id: s.repetitions for s in chosen}
    else:
        chosen = list(scenarios)
        rules.append(f"{profile.value}: all scenarios including HOLDOUT, repetitions >= 3")
        reps = {s.scenario_id: max(3, s.repetitions) for s in chosen}
        if profile is Profile.EXTENDED:
            rules.append("EXTENDED: V1 behaves as DEEP (adversarial sets arrive in V1.1)")
    if deterministic:
        reps = dict.fromkeys(reps, 1)
        rules.append("adapter is deterministic: repetitions collapsed to 1")
    if override is not None:
        reps = dict.fromkeys(reps, override)
        rules.append(f"repetitions overridden to {override}")
    return chosen, reps, rules


class CampaignRunner:
    def __init__(
        self,
        repo: SQLiteRepository,
        registry: EvaluatorRegistry | None = None,
        *,
        actor: str = "cli",
        timeout_s: float = DEFAULT_TIMEOUT_S,
        stop_on_eliminatory: bool = False,
    ) -> None:
        self.repo = repo
        self.registry = registry or DefaultEvaluatorRegistry()
        self.actor = actor
        self.timeout_s = timeout_s
        self.stop_on_eliminatory = stop_on_eliminatory

    # ------------------------------------------------------------------ planning
    def plan(
        self,
        project_dir: Path,
        agent_id: str,
        *,
        profile: Profile,
        seed: int | None = None,
        repetitions_override: int | None = None,
        dry_run: bool = False,
        baseline_campaign_id: str | None = None,
    ) -> PlannedCampaign:
        config = load_project(project_dir)
        if agent_id not in config.agents:
            msg = f"agent {agent_id!r} not in project {config.project_id!r}"
            raise CampaignRefusedError(msg)
        agent_cfg = config.agents[agent_id]
        adapter = create_adapter(agent_cfg.adapter, agent_cfg.version, agent_cfg.params)
        all_scenarios = [s for s in load_scenarios(project_dir, config) if s.agent_id == agent_id]
        if not all_scenarios:
            msg = f"no scenario for agent {agent_id!r}"
            raise CampaignRefusedError(msg)
        chosen, reps, rules = _select(
            all_scenarios, profile, adapter.capabilities.deterministic, repetitions_override
        )
        if not chosen:
            msg = f"profile {profile.value} selected no scenario"
            raise CampaignRefusedError(msg)
        if adapter.capabilities.cost_bearing and not dry_run:
            msg = (
                "cost-bearing adapters require the COST_CONTROLLER (Phase 3); "
                "refusing to run unmetered paid calls"
            )
            raise CampaignRefusedError(msg)
        planned = sum(reps.values())
        campaign = Campaign(
            campaign_id=new_id("cmp"),
            project_id=config.project_id,
            agent_id=agent_id,
            agent_version=adapter.agent_version,
            profile=profile,
            scenario_ids=[s.scenario_id for s in chosen],
            repetitions_override=repetitions_override,
            seed=seed if seed is not None else 0,
            plan=CampaignPlan(
                planned_runs=planned,
                expected_tokens=None,
                expected_agent_cost=0.0 if not adapter.capabilities.cost_bearing else None,
                uncertainty=(
                    "no historical usage: token forecast unavailable; cost is 0 for "
                    "non-cost-bearing adapters, UNKNOWN otherwise"
                ),
                basis="conservative_default",
            ),
            dry_run=dry_run,
            status=CampaignStatus.DRY_RUN if dry_run else CampaignStatus.PLANNED,
            baseline_campaign_id=baseline_campaign_id,
            created_at=utcnow(),
            evalkit_version=__version__,
        )
        return PlannedCampaign(campaign, config, chosen, reps, adapter, rules)

    # ----------------------------------------------------------------- execution
    def _emit(self, event_type: EventType, campaign: Campaign, **kw: Any) -> None:
        payload = kw.pop("payload", None)
        severity = kw.pop("severity", Severity.INFO)
        self.repo.emit(
            make_event(
                event_type,
                component="core",
                actor=self.actor,
                severity=severity,
                payload=payload,
                project_id=campaign.project_id,
                agent_id=campaign.agent_id,
                agent_version=campaign.agent_version,
                campaign_id=campaign.campaign_id,
                **kw,
            )
        )

    async def execute(self, planned: PlannedCampaign) -> Campaign:
        campaign = planned.campaign
        with self.repo.transaction():
            for s in planned.scenarios:
                self.repo.save_scenario(s)
            self.repo.save_campaign(campaign)
        self._emit(
            EventType.CAMPAIGN_STARTED,
            campaign,
            payload={
                "profile": campaign.profile.value,
                "dry_run": campaign.dry_run,
                "planned_runs": planned.planned_runs,
                "rules": planned.rules,
                "adapter": planned.adapter.capabilities.model_dump(mode="json"),
            },
        )
        if campaign.dry_run:
            campaign = campaign.model_copy(
                update={"status": CampaignStatus.DRY_RUN, "stop_reason": "dry run: no call made"}
            )
            self.repo.save_campaign(campaign)
            self._emit(EventType.CAMPAIGN_ENDED, campaign, status=campaign.status.value)
            return campaign

        campaign = campaign.model_copy(
            update={"status": CampaignStatus.RUNNING, "started_at": utcnow()}
        )
        self.repo.save_campaign(campaign)
        stop_reason: str | None = None
        final_status = CampaignStatus.COMPLETED
        try:
            for scenario in planned.scenarios:
                eliminatory = await self._run_scenario(planned, scenario)
                if eliminatory and self.stop_on_eliminatory:
                    stop_reason = f"eliminatory failure on {scenario.scenario_id}"
                    final_status = CampaignStatus.STOPPED_ELIMINATORY
                    break
        except Exception as exc:
            final_status = CampaignStatus.FAILED
            stop_reason = f"{type(exc).__name__}: {exc}"
            self._emit(
                EventType.ERROR, campaign, severity=Severity.ERROR, payload={"error": stop_reason}
            )
        campaign = campaign.model_copy(
            update={"status": final_status, "ended_at": utcnow(), "stop_reason": stop_reason}
        )
        self.repo.save_campaign(campaign)
        self._emit(
            EventType.CAMPAIGN_ENDED,
            campaign,
            status=final_status.value,
            payload={"stop_reason": stop_reason},
        )
        return campaign

    async def _run_scenario(self, planned: PlannedCampaign, scenario: Scenario) -> bool:
        campaign = planned.campaign
        eliminatory = False
        self._emit(
            EventType.SCENARIO_STARTED,
            campaign,
            payload={"scenario_id": scenario.scenario_id, "version": scenario.version},
        )
        for attempt in range(1, planned.repetitions[scenario.scenario_id] + 1):
            run = await self._run_once(planned, scenario, attempt)
            results = await self._evaluate(run, scenario)
            if any(r.blocking and r.status is EvalStatus.FAIL for r in results):
                eliminatory = True
        self._emit(
            EventType.SCENARIO_ENDED,
            campaign,
            payload={"scenario_id": scenario.scenario_id, "eliminatory_failure": eliminatory},
        )
        return eliminatory

    def _seed_for(self, campaign: Campaign, scenario: Scenario, attempt: int) -> int:
        base = f"{campaign.seed}:{scenario.scenario_id}:{scenario.version}:{attempt}"
        return int(hashlib.sha256(base.encode()).hexdigest()[:8], 16)

    async def _run_once(self, planned: PlannedCampaign, scenario: Scenario, attempt: int) -> Run:
        campaign = planned.campaign
        seed = self._seed_for(campaign, scenario, attempt)
        run = Run(
            run_id=new_id("run"),
            campaign_id=campaign.campaign_id,
            scenario_id=scenario.scenario_id,
            scenario_version=scenario.version,
            project_id=campaign.project_id,
            agent_id=campaign.agent_id,
            agent_version=campaign.agent_version,
            attempt=attempt,
            seed=seed,
            status=RunStatus.RUNNING,
            started_at=utcnow(),
        )
        self.repo.save_run(run)
        self._emit(
            EventType.AGENT_CALLED,
            campaign,
            run_id=run.run_id,
            payload={"scenario_id": scenario.scenario_id, "attempt": attempt, "seed": seed},
        )
        timeout = (
            scenario.budget.max_latency_ms / 1000 if scenario.budget.max_latency_ms else None
        ) or self.timeout_s
        started = utcnow()
        try:
            response = await asyncio.wait_for(
                planned.adapter.invoke(scenario, seed=seed, timeout_s=timeout), timeout=timeout
            )
        except TimeoutError:
            run = run.model_copy(
                update={
                    "status": RunStatus.TIMEOUT,
                    "ended_at": utcnow(),
                    "error": f"timeout after {timeout}s",
                }
            )
            self.repo.save_run(run)
            self._emit(
                EventType.ERROR,
                campaign,
                run_id=run.run_id,
                severity=Severity.WARNING,
                payload={"error": run.error},
            )
            return run
        ended = utcnow()
        latency = response.latency_ms
        if latency is None:
            latency = (ended - started).total_seconds() * 1000
        steps = [TrajectoryStep.model_validate(s) for s in response.trajectory_steps]
        trajectory = Trajectory(
            run_id=run.run_id,
            steps=steps,
            terminal_state=steps[-1].next_state or steps[-1].state if steps else None,
            completed=bool(steps) and steps[-1].kind.value == "terminal",
        )
        error = response.metadata.get("error")
        output_ref = None
        if response.output is not None:
            import json

            output_ref = self.repo.put_artifact(
                json.dumps(response.output, default=str, ensure_ascii=False).encode(), kind="json"
            )
        run = run.model_copy(
            update={
                "status": RunStatus.ERRORED if error else RunStatus.COMPLETED,
                "ended_at": ended,
                "latency_ms": latency,
                "output": response.output,
                "output_ref": output_ref,
                "usage": response.usage,
                "trajectory": trajectory,
                "error": str(error) if error else None,
            }
        )
        self.repo.save_run(run)
        for usage in response.usage:
            self.repo.emit(
                make_event(
                    EventType.USAGE_RECORDED,
                    component="core",
                    actor=self.actor,
                    project_id=campaign.project_id,
                    agent_id=campaign.agent_id,
                    agent_version=campaign.agent_version,
                    campaign_id=campaign.campaign_id,
                    run_id=run.run_id,
                    usage=usage,
                    payload={"source": usage.source.value},
                )
            )
        for step in steps:
            if step.tool_name:
                self._emit(
                    EventType.TOOL_CALLED,
                    campaign,
                    run_id=run.run_id,
                    payload={"tool": step.tool_name, "step": step.index},
                )
            if step.kind.value == "retry":
                self._emit(
                    EventType.RETRY, campaign, run_id=run.run_id, payload={"step": step.index}
                )
        if error:
            self._emit(
                EventType.ERROR,
                campaign,
                run_id=run.run_id,
                severity=Severity.WARNING,
                payload={"error": str(error)},
            )
        return run

    async def _evaluate(self, run: Run, scenario: Scenario) -> list[EvaluationResult]:
        results: list[EvaluationResult] = []
        for spec in scenario.verifications:
            try:
                evaluator = self.registry.get(spec.evaluator)
                result = await evaluator.evaluate(run, scenario, spec)
            except Exception as exc:
                result = EvaluationResult(
                    result_id=new_id("res"),
                    run_id=run.run_id,
                    evaluator_id=spec.evaluator,
                    evaluator_version="unknown",
                    dimension=spec.dimension,
                    control_state=ControlState.ERRORED,
                    status=EvalStatus.NOT_EVALUATED,
                    measurement=MeasurementKind.UNAVAILABLE,
                    blocking=spec.blocking,
                    message=f"evaluator fault: {type(exc).__name__}: {exc}",
                    evaluated_at=utcnow(),
                )
            self.repo.save_result(result)
            self.repo.emit(
                make_event(
                    EventType.EVALUATION_RESULT,
                    component="core",
                    actor=self.actor,
                    project_id=run.project_id,
                    agent_id=run.agent_id,
                    agent_version=run.agent_version,
                    campaign_id=run.campaign_id,
                    run_id=run.run_id,
                    status=result.status.value,
                    payload={
                        "evaluator": result.evaluator_id,
                        "dimension": result.dimension.value,
                        "control_state": result.control_state.value,
                        "blocking": result.blocking,
                        "result_id": result.result_id,
                    },
                )
            )
            results.append(result)
        return results
