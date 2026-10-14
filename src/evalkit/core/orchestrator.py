"""Campaign orchestrator: scenario → run → evaluation → audit, persisted step by step.

Phase 3: TOKEN_METER records every usage with attribution and cost; COST_CONTROLLER
reserves before each cost-bearing run and settles after; a BLOCK stops the campaign
(STOPPED_BUDGET). Scenarios may run concurrently under a bounded semaphore; runs of one
scenario stay sequential. Profiles QUICK/STANDARD/DEEP/EXTENDED with explicit V1 rules,
DRY_RUN, eliminatory early-stop (opt-in).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from typing import Any

from evalkit import __version__
from evalkit.adapters import AgentAdapter, create_adapter
from evalkit.audit import make_event
from evalkit.contracts import (
    Campaign,
    CampaignStatus,
    ControlState,
    Cost,
    CostStatus,
    Criticality,
    DatasetKind,
    EvalStatus,
    EvaluationResult,
    EventType,
    MeasurementKind,
    PriceEntry,
    Profile,
    Run,
    RunStatus,
    Scenario,
    Severity,
    TokenUsage,
    Trajectory,
    TrajectoryStep,
    new_id,
    utcnow,
)
from evalkit.core.project import ProjectConfig, load_project, load_scenarios
from evalkit.cost_controller import BudgetDecision, SQLiteCostController, compute_cost
from evalkit.evaluators import DefaultEvaluatorRegistry, EvaluatorRegistry
from evalkit.storage.sqlite import SQLiteRepository
from evalkit.token_meter import SQLiteTokenMeter, UsageAttribution

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
    price: PriceEntry | None = None
    all_scenarios: list[Scenario] = field(default_factory=list)
    """Every scenario of the agent (run or not): persisted for coverage controls."""

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


def _merge_costs(costs: list[Cost]) -> Cost | None:
    if not costs:
        return None
    statuses = {c.status for c in costs}
    known = [c for c in costs if c.amount is not None]
    amount = sum((c.amount for c in known if c.amount is not None), Decimal(0)) if known else None
    currency = next((c.currency for c in known if c.currency), None)
    if CostStatus.UNKNOWN in statuses:
        status = CostStatus.UNKNOWN
        note = f"{len(costs) - len(known)} of {len(costs)} usage records without cost"
    elif CostStatus.ESTIMATED in statuses:
        status, note = CostStatus.ESTIMATED, "contains estimated components"
    else:
        status, note = CostStatus.MEASURED, None
    return Cost(
        status=status,
        amount=amount if status is not CostStatus.UNKNOWN or known else None,
        currency=currency,
        price_id=next((c.price_id for c in known if c.price_id), None),
        note=note,
    )


class CampaignRunner:
    def __init__(
        self,
        repo: SQLiteRepository,
        registry: EvaluatorRegistry | None = None,
        *,
        actor: str = "cli",
        timeout_s: float = DEFAULT_TIMEOUT_S,
        stop_on_eliminatory: bool = False,
        max_workers: int = 1,
    ) -> None:
        self.repo = repo
        self.registry = registry or DefaultEvaluatorRegistry()
        self.actor = actor
        self.timeout_s = timeout_s
        self.stop_on_eliminatory = stop_on_eliminatory
        self.max_workers = max(1, max_workers)
        self.meter = SQLiteTokenMeter(repo)
        self.controller = SQLiteCostController(repo, actor=actor)
        self._budget_blocked = False

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
        planned_runs = sum(reps.values())
        created_at = utcnow()
        cost_bearing = adapter.capabilities.cost_bearing
        # Price snapshot (frozen for the campaign) when the adapter exposes provider/model.
        price: PriceEntry | None = None
        provider = getattr(adapter, "provider", None)
        model = getattr(adapter, "model", None)
        if isinstance(provider, str) and isinstance(model, str):
            price = self.repo.find_price(provider, model, created_at.date().isoformat())
        history = self.meter.per_run_history(config.project_id, agent_id) if cost_bearing else []
        hint = (
            float(price.input_per_million + (price.output_per_million or 0))
            if price and price.input_per_million is not None
            else None
        )
        campaign = Campaign(
            campaign_id=new_id("cmp"),
            project_id=config.project_id,
            agent_id=agent_id,
            agent_version=adapter.agent_version,
            profile=profile,
            scenario_ids=[s.scenario_id for s in chosen],
            repetitions_override=repetitions_override,
            seed=seed if seed is not None else 0,
            plan=self.controller.forecast(
                None,
                planned_runs=planned_runs,
                cost_bearing=cost_bearing,
                history_tokens=history,
                price_per_million_hint=hint,
            ),
            dry_run=dry_run,
            status=CampaignStatus.DRY_RUN if dry_run else CampaignStatus.PLANNED,
            baseline_campaign_id=baseline_campaign_id,
            price_snapshot_ids=[price.price_id] if price else [],
            created_at=created_at,
            evalkit_version=__version__,
        )
        if cost_bearing and not dry_run and not self.controller.applicable_budgets(campaign):
            msg = (
                "cost-bearing adapter with no applicable budget: define one with "
                "`evalkit budget set` (no implicit default budget exists)"
            )
            raise CampaignRefusedError(msg)
        return PlannedCampaign(campaign, config, chosen, reps, adapter, rules, price, all_scenarios)

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
        self._budget_blocked = False
        with self.repo.transaction():
            for s in planned.all_scenarios or planned.scenarios:
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
                "plan": campaign.plan.model_dump(mode="json") if campaign.plan else None,
                "price_snapshot_ids": campaign.price_snapshot_ids,
                "max_workers": self.max_workers,
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
        eliminatory_hit = asyncio.Event()
        sem = asyncio.Semaphore(self.max_workers)

        async def one(scenario: Scenario) -> None:
            async with sem:
                if (eliminatory_hit.is_set() and self.stop_on_eliminatory) or self._budget_blocked:
                    return
                if await self._run_scenario(planned, scenario):
                    eliminatory_hit.set()

        try:
            await asyncio.gather(*(one(s) for s in planned.scenarios))
            if self._budget_blocked:
                final_status = CampaignStatus.STOPPED_BUDGET
                stop_reason = "budget cap reached: no further call allowed"
            elif eliminatory_hit.is_set() and self.stop_on_eliminatory:
                final_status = CampaignStatus.STOPPED_ELIMINATORY
                stop_reason = "eliminatory failure: campaign stopped early"
        except Exception as exc:
            final_status = CampaignStatus.FAILED
            stop_reason = f"{type(exc).__name__}: {exc}"
            self._emit(
                EventType.ERROR, campaign, severity=Severity.ERROR, payload={"error": stop_reason}
            )
        released = self.controller.release_stale(campaign.campaign_id)
        campaign = campaign.model_copy(
            update={"status": final_status, "ended_at": utcnow(), "stop_reason": stop_reason}
        )
        self.repo.save_campaign(campaign)
        self._emit(
            EventType.CAMPAIGN_ENDED,
            campaign,
            status=final_status.value,
            payload={"stop_reason": stop_reason, "stale_reservations_released": released},
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
            if self._budget_blocked or (eliminatory and self.stop_on_eliminatory):
                break
            run = await self._run_once(planned, scenario, attempt)
            if run.status is RunStatus.BUDGET_BLOCKED:
                break
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

    def _expected_per_run(self, planned: PlannedCampaign) -> tuple[float, int | None]:
        plan = planned.campaign.plan
        if plan is None or planned.planned_runs == 0:
            return 0.0, None
        cost = (plan.expected_agent_cost or 0.0) / planned.planned_runs
        tokens = (plan.expected_tokens // planned.planned_runs) if plan.expected_tokens else None
        return cost, tokens

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
        reservation_id: str | None = None
        if planned.adapter.capabilities.cost_bearing:
            exp_cost, exp_tokens = self._expected_per_run(planned)
            decision, reservation = self.controller.reserve(
                campaign, run_id=run.run_id, expected_cost=exp_cost, expected_tokens=exp_tokens
            )
            if decision is BudgetDecision.BLOCK or reservation is None:
                self._budget_blocked = True
                run = run.model_copy(
                    update={
                        "status": RunStatus.BUDGET_BLOCKED,
                        "ended_at": utcnow(),
                        "error": "budget blocked before call",
                    }
                )
                self.repo.save_run(run)
                return run
            reservation_id = reservation.reservation_id
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
            if reservation_id:
                # the provider may still bill an accepted call: settle with the reservation
                self.controller.settle(
                    reservation_id, Cost.unknown("timeout: observed cost unknown")
                )
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
            output_ref = self.repo.put_artifact(
                json.dumps(response.output, default=str, ensure_ascii=False).encode(), kind="json"
            )
        costs = self._meter_usages(campaign, run, scenario, response.usage, planned.price)
        run_cost = _merge_costs(costs)
        run = run.model_copy(
            update={
                "status": RunStatus.ERRORED if error else RunStatus.COMPLETED,
                "ended_at": ended,
                "latency_ms": latency,
                "output": response.output,
                "output_ref": output_ref,
                "usage": response.usage,
                "cost": run_cost,
                "trajectory": trajectory,
                "error": str(error) if error else None,
            }
        )
        self.repo.save_run(run)
        if reservation_id:
            tokens = sum(u.billable_total() or 0 for u in response.usage) or None
            self.controller.settle(
                reservation_id, run_cost or Cost.unknown("no usage returned"), tokens
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

    def _meter_usages(
        self,
        campaign: Campaign,
        run: Run,
        scenario: Scenario,
        usages: list[TokenUsage],
        price: PriceEntry | None,
        *,
        evaluator_id: str | None = None,
    ) -> list[Cost]:
        costs: list[Cost] = []
        for i, usage in enumerate(usages):
            entry = price
            if entry is None or entry.provider != usage.provider or entry.model_id != usage.model:
                entry = self.repo.find_price(
                    usage.provider, usage.model, campaign.created_at.date().isoformat()
                )
            cost = compute_cost(usage, entry)
            costs.append(cost)
            self.meter.record(
                usage,
                UsageAttribution(
                    project_id=campaign.project_id,
                    agent_id=campaign.agent_id,
                    agent_version=campaign.agent_version,
                    campaign_id=campaign.campaign_id,
                    scenario_id=scenario.scenario_id,
                    run_id=run.run_id,
                    call_id=f"{run.run_id}:{evaluator_id or 'agent'}:{i}",
                    evaluator_id=evaluator_id,
                    period=campaign.created_at.date().isoformat(),
                ),
                cost,
            )
            self.repo.emit(
                make_event(
                    EventType.USAGE_RECORDED,
                    component="token_meter",
                    actor=self.actor,
                    project_id=campaign.project_id,
                    agent_id=campaign.agent_id,
                    agent_version=campaign.agent_version,
                    campaign_id=campaign.campaign_id,
                    run_id=run.run_id,
                    usage=usage,
                    cost=cost,
                    payload={"source": usage.source.value, "evaluator_id": evaluator_id},
                )
            )
        return costs

    async def _evaluate(self, run: Run, scenario: Scenario) -> list[EvaluationResult]:
        campaign = self.repo.get_campaign(run.campaign_id)
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
            if result.evaluator_usage:
                costs = self._meter_usages(
                    campaign,
                    run,
                    scenario,
                    result.evaluator_usage,
                    None,
                    evaluator_id=result.evaluator_id,
                )
                result = result.model_copy(update={"evaluator_cost": _merge_costs(costs)})
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
