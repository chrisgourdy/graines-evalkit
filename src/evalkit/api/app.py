"""EVALKIT HTTP API, versioned under ``/v1`` — a thin layer over ``evalkit.core``.

Security defaults: binds 127.0.0.1; every request (except ``/v1/health``) requires the
``X-EvalKit-Key`` header matching ``EVALKIT_API_KEY``; when that variable is unset the API
answers 503 rather than running open. Each request opens its own SQLite connection; campaign
execution runs in a worker thread with its own connection (SQLite serialises writers).
Agent outputs returned by the API are untrusted data for clients, as everywhere in EVALKIT.
"""

from __future__ import annotations

import asyncio
import hmac
import os
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from pydantic import BaseModel, Field

from evalkit import __version__
from evalkit.contracts import (
    CONTRACT_SCHEMA_VERSION,
    AuditEvent,
    Campaign,
    EvaluationResult,
    Profile,
    Run,
    Scorecard,
    TokenUsage,
    utcnow,
)
from evalkit.core import CampaignRefusedError, CampaignRunner, ScenarioLoadError
from evalkit.storage import NotFoundError, SQLiteRepository


class Settings:
    def __init__(self) -> None:
        self.data_dir = Path(os.environ.get("EVALKIT_DATA_DIR", "data"))
        self.projects_dir = Path(os.environ.get("EVALKIT_PROJECTS_DIR", "projects"))
        self.api_key = os.environ.get("EVALKIT_API_KEY")


def _settings() -> Settings:
    return Settings()


def _auth(
    settings: Settings = Depends(_settings),
    x_evalkit_key: str | None = Header(default=None),
) -> None:
    if not settings.api_key:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            "EVALKIT_API_KEY is not configured: the API refuses to run open",
        )
    if not x_evalkit_key or not hmac.compare_digest(x_evalkit_key, settings.api_key):
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid or missing X-EvalKit-Key")


def _repo(settings: Settings = Depends(_settings)) -> Iterator[SQLiteRepository]:
    repo = SQLiteRepository(settings.data_dir)
    repo.migrate()
    try:
        yield repo
    finally:
        repo.close()


class CampaignRequest(BaseModel):
    project_id: str
    agent_id: str
    profile: Profile = Profile.STANDARD
    seed: int | None = None
    repetitions: int | None = None
    dry_run: bool = False
    baseline_campaign_id: str | None = None
    workers: int = Field(default=1, ge=1, le=16)
    stop_on_eliminatory: bool = False


class UsagePush(BaseModel):
    """External usage record (e.g. a JS agent instrumented with the SDK)."""

    project_id: str
    usage: TokenUsage
    agent_id: str | None = None
    agent_version: str | None = None
    campaign_id: str | None = None
    scenario_id: str | None = None
    run_id: str | None = None
    evaluator_id: str | None = None
    call_id: str | None = None


class EventPush(BaseModel):
    event_type: str
    component: str = "sdk"
    actor: str = "api:sdk"
    severity: str = "INFO"
    project_id: str | None = None
    agent_id: str | None = None
    campaign_id: str | None = None
    run_id: str | None = None
    trace_id: str | None = None
    span_id: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


def create_app() -> FastAPI:
    app = FastAPI(
        title="EVALKIT API",
        version=__version__,
        description="Evaluation, observability and continuous improvement of AI agents.",
    )
    protected = [Depends(_auth)]

    @app.get("/v1/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "evalkit": __version__, "contracts": CONTRACT_SCHEMA_VERSION}

    @app.get("/v1/projects/{project_id}/campaigns", dependencies=protected)
    def list_campaigns(
        project_id: str,
        agent_id: str | None = Query(default=None),
        repo: SQLiteRepository = Depends(_repo),
    ) -> list[Campaign]:
        return list(repo.list_campaigns(project_id, agent_id))

    @app.post("/v1/campaigns", status_code=status.HTTP_202_ACCEPTED, dependencies=protected)
    def launch_campaign(
        req: CampaignRequest,
        settings: Settings = Depends(_settings),
    ) -> Campaign:
        project_dir = settings.projects_dir / req.project_id
        if not (project_dir / "evalkit.yaml").is_file():
            raise HTTPException(status.HTTP_404_NOT_FOUND, f"unknown project {req.project_id!r}")
        repo = SQLiteRepository(settings.data_dir)
        repo.migrate()
        runner = CampaignRunner(
            repo, actor="api", max_workers=req.workers, stop_on_eliminatory=req.stop_on_eliminatory
        )
        try:
            planned = runner.plan(
                project_dir,
                req.agent_id,
                profile=req.profile,
                seed=req.seed,
                repetitions_override=req.repetitions,
                dry_run=req.dry_run,
                baseline_campaign_id=req.baseline_campaign_id,
            )
        except (CampaignRefusedError, ScenarioLoadError, KeyError) as exc:
            repo.close()
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
        # Persist PLANNED state now so the client can poll immediately.
        with repo.transaction():
            repo.save_campaign(planned.campaign)

        def _work() -> None:
            try:
                asyncio.run(runner.execute(planned))
            finally:
                repo.close()

        threading.Thread(
            target=_work, name=f"campaign-{planned.campaign.campaign_id}", daemon=True
        ).start()
        return planned.campaign

    @app.get("/v1/campaigns/{campaign_id}", dependencies=protected)
    def get_campaign(campaign_id: str, repo: SQLiteRepository = Depends(_repo)) -> Campaign:
        try:
            return repo.get_campaign(campaign_id)
        except NotFoundError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "campaign not found") from exc

    @app.get("/v1/campaigns/{campaign_id}/runs", dependencies=protected)
    def get_runs(campaign_id: str, repo: SQLiteRepository = Depends(_repo)) -> list[Run]:
        return list(repo.list_runs(campaign_id))

    @app.get("/v1/campaigns/{campaign_id}/results", dependencies=protected)
    def get_results(
        campaign_id: str,
        repo: SQLiteRepository = Depends(_repo),
    ) -> list[EvaluationResult]:
        return [res for run in repo.list_runs(campaign_id) for res in repo.list_results(run.run_id)]

    @app.get("/v1/campaigns/{campaign_id}/scorecard", dependencies=protected)
    def get_scorecard(campaign_id: str, repo: SQLiteRepository = Depends(_repo)) -> Scorecard:
        from evalkit.scoring import build_scorecard

        try:
            campaign = repo.get_campaign(campaign_id)
        except NotFoundError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "campaign not found") from exc
        if campaign.status.value in ("PLANNED", "RUNNING", "DRY_RUN"):
            raise HTTPException(status.HTTP_409_CONFLICT, f"campaign is {campaign.status.value}")
        return repo.scorecard_for_campaign(campaign_id) or build_scorecard(repo, campaign_id)

    @app.get("/v1/campaigns/{campaign_id}/report", dependencies=protected)
    def get_report(campaign_id: str, repo: SQLiteRepository = Depends(_repo)) -> dict[str, Any]:
        from evalkit.reporting import build_report

        try:
            return build_report(repo, campaign_id)
        except NotFoundError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "campaign not found") from exc

    @app.get("/v1/campaigns/{campaign_id}/events", dependencies=protected)
    def get_events(campaign_id: str, repo: SQLiteRepository = Depends(_repo)) -> list[AuditEvent]:
        return list(repo.query(campaign_id=campaign_id))

    @app.post("/v1/usage", status_code=status.HTTP_201_CREATED, dependencies=protected)
    def push_usage(req: UsagePush, repo: SQLiteRepository = Depends(_repo)) -> dict[str, str]:
        from evalkit.cost_controller import compute_cost
        from evalkit.token_meter import SQLiteTokenMeter, UsageAttribution

        price = repo.find_price(req.usage.provider, req.usage.model, utcnow().date().isoformat())
        cost = compute_cost(req.usage, price)
        usage_id = SQLiteTokenMeter(repo).record(
            req.usage,
            UsageAttribution(
                project_id=req.project_id,
                agent_id=req.agent_id,
                agent_version=req.agent_version,
                campaign_id=req.campaign_id,
                scenario_id=req.scenario_id,
                run_id=req.run_id,
                evaluator_id=req.evaluator_id,
                call_id=req.call_id,
            ),
            cost,
        )
        return {"usage_id": usage_id, "cost_status": cost.status.value}

    @app.post("/v1/events", status_code=status.HTTP_201_CREATED, dependencies=protected)
    def push_event(req: EventPush, repo: SQLiteRepository = Depends(_repo)) -> dict[str, Any]:
        from evalkit.audit import make_event
        from evalkit.contracts import EventType, Severity

        try:
            event_type = EventType(req.event_type)
            severity = Severity(req.severity)
        except ValueError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
        if event_type in (
            EventType.PERMISSION_CHANGED,
            EventType.VALIDATION_DECISION,
            EventType.BASELINE_CHANGED,
        ):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, "governance events cannot be pushed through the API"
            )
        event = repo.emit(
            make_event(
                event_type,
                component=req.component[:40],
                actor=f"api:{req.actor[:40]}",
                severity=severity,
                payload={**req.payload, "pushed": True},
                project_id=req.project_id,
                agent_id=req.agent_id,
                campaign_id=req.campaign_id,
                run_id=req.run_id,
                trace_id=req.trace_id,
                span_id=req.span_id,
            )
        )
        return {"event_id": event.event_id, "sequence": event.sequence}

    @app.get("/v1/schemas", dependencies=protected)
    def schemas() -> dict[str, Any]:
        from evalkit.contracts.schema_export import _exported_models

        return {name: model.model_json_schema() for name, model in _exported_models().items()}

    return app


app = create_app()
