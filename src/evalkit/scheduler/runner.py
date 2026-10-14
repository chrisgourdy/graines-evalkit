"""Scheduler runtime: due jobs → campaign → scorecard → (retrofit → apply → confirm) with guards.

Independent of any Cowork session: ``evalkit schedule run plan.yaml --once`` fits a cron or
systemd timer, the loop mode fits a container. State lives in the database
(``schedule_state``), so a killed scheduler resumes its interrupted campaign on the next tick
instead of starting a new one. One scheduler per data directory (lock file).
"""

from __future__ import annotations

import asyncio
import json
import os
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from evalkit.audit import make_event
from evalkit.contracts import (
    Budget,
    BudgetScope,
    Campaign,
    CampaignStatus,
    EvalStatus,
    EventType,
    Severity,
    utcnow,
)
from evalkit.core.orchestrator import CampaignRunner
from evalkit.improvement import ApplyRefusedError, RetrofitCycle, apply_fix, rollback
from evalkit.scheduler.plan import ScheduledJob, SchedulePlan
from evalkit.scoring import build_scorecard
from evalkit.storage.sqlite import SQLiteRepository

LOCK_NAME = "scheduler.lock"


class SchedulerLockedError(RuntimeError):
    pass


@dataclass
class JobState:
    job_name: str
    plan_id: str
    last_run_at: datetime | None = None
    last_campaign_id: str | None = None
    running_campaign_id: str | None = None
    last_good_campaign_id: str | None = None
    consecutive_failures: int = 0
    retrofit_day: str | None = None
    retrofits_today: int = 0
    last_retrofit_at: datetime | None = None
    paused_reason: str | None = None
    history: list[dict[str, Any]] = field(default_factory=list)

    def is_paused(self) -> bool:
        return self.paused_reason is not None


@dataclass
class JobOutcome:
    job: str
    action: str
    """ran | resumed | skipped_not_due | skipped_paused | failed"""
    campaign_id: str | None = None
    scorecard_status: str | None = None
    retrofit_decision: str | None = None
    applied: bool = False
    confirmed: str | None = None
    note: str = ""


def _dt(value: str | None) -> datetime | None:
    return datetime.fromisoformat(value) if value else None


class SchedulerLock:
    def __init__(self, data_dir: Path) -> None:
        self.path = Path(data_dir) / LOCK_NAME
        self._fd: int | None = None

    def __enter__(self) -> SchedulerLock:
        try:
            self._fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            pid = self._pid()
            if pid and _alive(pid):
                msg = f"another scheduler (pid {pid}) holds {self.path}"
                raise SchedulerLockedError(msg) from None
            self.path.unlink(missing_ok=True)  # stale lock of a dead process
            self._fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        os.write(self._fd, str(os.getpid()).encode())
        return self

    def __exit__(self, *_: object) -> None:
        if self._fd is not None:
            os.close(self._fd)
        self.path.unlink(missing_ok=True)

    def _pid(self) -> int | None:
        try:
            return int(self.path.read_text().strip() or 0) or None
        except (OSError, ValueError):
            return None


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


class Scheduler:
    def __init__(
        self, repo: SQLiteRepository, plan: SchedulePlan, *, actor: str | None = None
    ) -> None:
        self.repo = repo
        self.plan = plan
        self.actor = actor or f"scheduler:{plan.plan_id}"

    # ----------------------------------------------------------------- state
    def state(self, job: ScheduledJob) -> JobState:
        row = self.repo._conn.execute(
            "SELECT * FROM schedule_state WHERE job_name=? AND plan_id=?",
            (job.name, self.plan.plan_id),
        ).fetchone()
        if row is None:
            return JobState(job.name, self.plan.plan_id)
        extra = json.loads(row["json"])
        return JobState(
            job_name=row["job_name"],
            plan_id=row["plan_id"],
            last_run_at=_dt(row["last_run_at"]),
            last_campaign_id=row["last_campaign_id"],
            running_campaign_id=row["running_campaign_id"],
            last_good_campaign_id=row["last_good_campaign_id"],
            consecutive_failures=int(row["consecutive_failures"]),
            retrofit_day=row["retrofit_day"],
            retrofits_today=int(row["retrofits_today"]),
            last_retrofit_at=_dt(row["last_retrofit_at"]),
            paused_reason=row["paused_reason"],
            history=list(extra.get("history", [])),
        )

    def save_state(self, st: JobState) -> None:
        st.history = st.history[-50:]
        with self.repo.transaction():
            self.repo._conn.execute(
                "INSERT OR REPLACE INTO schedule_state(job_name, plan_id, updated_at, last_run_at,"
                " last_campaign_id, running_campaign_id, last_good_campaign_id,"
                " consecutive_failures, retrofit_day, retrofits_today, last_retrofit_at,"
                " paused_reason, json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    st.job_name,
                    st.plan_id,
                    utcnow().isoformat(),
                    st.last_run_at.isoformat() if st.last_run_at else None,
                    st.last_campaign_id,
                    st.running_campaign_id,
                    st.last_good_campaign_id,
                    st.consecutive_failures,
                    st.retrofit_day,
                    st.retrofits_today,
                    st.last_retrofit_at.isoformat() if st.last_retrofit_at else None,
                    st.paused_reason,
                    json.dumps({"history": st.history}, sort_keys=True),
                ),
            )

    def states(self) -> list[JobState]:
        return [self.state(j) for j in self.plan.jobs]

    def resume_job(self, job_name: str, *, actor: str = "human", note: str = "") -> JobState:
        job = self._job(job_name)
        st = self.state(job)
        st.paused_reason = None
        st.consecutive_failures = 0
        st.history.append({"at": utcnow().isoformat(), "event": "resumed_by_human", "note": note})
        self.save_state(st)
        self._emit(
            EventType.HUMAN_INTERVENTION,
            job,
            payload={"action": "schedule.resume_job", "note": note},
            actor=actor,
        )
        return st

    def _job(self, name: str) -> ScheduledJob:
        for j in self.plan.jobs:
            if j.name == name:
                return j
        msg = f"no job {name!r} in plan {self.plan.plan_id!r}"
        raise KeyError(msg)

    # ----------------------------------------------------------------- events
    def _emit(
        self,
        event_type: EventType,
        job: ScheduledJob,
        *,
        payload: dict[str, Any],
        severity: Severity = Severity.INFO,
        actor: str | None = None,
        campaign: Campaign | None = None,
    ) -> None:
        ids: dict[str, Any] = {}
        if campaign is not None:
            ids = {
                "project_id": campaign.project_id,
                "agent_id": campaign.agent_id,
                "agent_version": campaign.agent_version,
                "campaign_id": campaign.campaign_id,
            }
        self.repo.emit(
            make_event(
                event_type,
                component="scheduler",
                actor=actor or self.actor,
                severity=severity,
                payload={"plan_id": self.plan.plan_id, "job": job.name, **payload},
                **ids,
            )
        )

    # ------------------------------------------------------------------ tick
    def due(self, job: ScheduledJob, st: JobState, now: datetime) -> bool:
        if st.running_campaign_id:
            return True
        if st.last_run_at is None:
            return True
        return now >= st.last_run_at + timedelta(minutes=job.interval_minutes)

    def tick(self, now: datetime | None = None) -> list[JobOutcome]:
        now = now or utcnow()
        outcomes: list[JobOutcome] = []
        for job in self.plan.jobs:
            st = self.state(job)
            if st.is_paused():
                outcomes.append(JobOutcome(job.name, "skipped_paused", note=st.paused_reason or ""))
                continue
            if not self.due(job, st, now):
                outcomes.append(JobOutcome(job.name, "skipped_not_due"))
                continue
            try:
                outcome = self._run_job(job, st, now)
                st.consecutive_failures = 0
            except Exception as exc:  # the loop must survive one broken job
                st.consecutive_failures += 1
                st.running_campaign_id = None
                note = f"{type(exc).__name__}: {exc}"
                outcome = JobOutcome(job.name, "failed", note=note)
                severity = Severity.ERROR
                if st.consecutive_failures >= job.max_consecutive_failures:
                    st.paused_reason = (
                        f"paused after {st.consecutive_failures} consecutive failures: {note}"
                    )
                    severity = Severity.CRITICAL
                self._emit(
                    EventType.ERROR,
                    job,
                    severity=severity,
                    payload={
                        "error": note,
                        "consecutive_failures": st.consecutive_failures,
                        "paused": st.is_paused(),
                    },
                )
                if st.is_paused():
                    self._emit(
                        EventType.HUMAN_INTERVENTION,
                        job,
                        severity=Severity.CRITICAL,
                        payload={
                            "action": "schedule.job_paused",
                            "reason": st.paused_reason,
                            "how_to_resume": "evalkit schedule resume-job <plan> <job>",
                        },
                    )
            st.last_run_at = now
            st.history.append(
                {
                    "at": now.isoformat(),
                    "action": outcome.action,
                    "campaign_id": outcome.campaign_id,
                    "scorecard": outcome.scorecard_status,
                    "retrofit": outcome.retrofit_decision,
                    "applied": outcome.applied,
                    "confirmed": outcome.confirmed,
                    "note": outcome.note[:300],
                }
            )
            self.save_state(st)
            outcomes.append(outcome)
        return outcomes

    def run_forever(self, *, poll_seconds: float = 60.0, max_ticks: int | None = None) -> int:
        ticks = 0
        while max_ticks is None or ticks < max_ticks:
            self.tick()
            ticks += 1
            if max_ticks is not None and ticks >= max_ticks:
                break
            time.sleep(poll_seconds)
        return ticks

    # ------------------------------------------------------------------- job
    def _run_job(self, job: ScheduledJob, st: JobState, now: datetime) -> JobOutcome:
        runner = CampaignRunner(self.repo, actor=self.actor, max_workers=job.workers)
        baseline = self._baseline(job, st)
        resumed = False
        if st.running_campaign_id:
            campaign = self.repo.get_campaign(st.running_campaign_id)
            if campaign.status in CampaignRunner.RESUMABLE:
                planned = runner.resume(job.project_dir, campaign.campaign_id)
                resumed = True
            else:  # it actually finished before the crash: nothing to resume
                planned = None
                st.running_campaign_id = None
        else:
            planned = None
        if planned is None:
            planned = runner.plan(
                job.project_dir,
                job.agent,
                profile=job.profile,
                seed=job.seed,
                baseline_campaign_id=baseline,
            )
            if job.max_cost_per_cycle is not None:
                runner.controller.save_budget(
                    Budget(
                        budget_id=f"sched-{planned.campaign.campaign_id}",
                        scope=BudgetScope.CAMPAIGN,
                        scope_ref=planned.campaign.campaign_id,
                        max_cost=job.max_cost_per_cycle,
                    )
                )
        st.running_campaign_id = planned.campaign.campaign_id
        self.save_state(st)  # durable before the long step: a crash here is resumable
        self._emit(
            EventType.CONFIG_CHANGED,
            job,
            payload={"action": "schedule.job_started", "resumed": resumed, "baseline": baseline},
            campaign=planned.campaign,
        )
        campaign = asyncio.run(runner.execute(planned))
        st.running_campaign_id = None
        st.last_campaign_id = campaign.campaign_id
        outcome = JobOutcome(job.name, "resumed" if resumed else "ran", campaign.campaign_id)
        if campaign.status is not CampaignStatus.COMPLETED:
            outcome.note = f"campaign {campaign.status.value}: {campaign.stop_reason}"
            self.save_state(st)
            return outcome
        card = build_scorecard(
            self.repo, campaign.campaign_id, weights=planned.config.weights or None
        )
        outcome.scorecard_status = card.overall_status.value
        healthy = (
            card.overall_status in (EvalStatus.PASS, EvalStatus.WARNING) and not card.regressions
        )
        if healthy:
            st.last_good_campaign_id = campaign.campaign_id
            self.save_state(st)
            return outcome
        if not job.retrofit:
            outcome.note = "incident detected; retrofit disabled for this job"
            self.save_state(st)
            return outcome
        if baseline is None:
            outcome.note = "incident detected; no known-good baseline yet: retrofit skipped"
            self.save_state(st)
            return outcome
        guard = self._retrofit_guard(job, st, now)
        if guard:
            outcome.note = guard
            self.save_state(st)
            return outcome
        self._count_retrofit(st, now)
        self.save_state(st)
        res = RetrofitCycle(
            self.repo,
            actor=self.actor,
            max_iterations=job.max_retrofit_iterations,
            seed=job.seed or 0,
        ).run(
            job.project_dir,
            job.agent,
            broken_campaign_id=campaign.campaign_id,
            good_campaign_id=baseline,
        )
        outcome.retrofit_decision = res.decision
        outcome.note = res.rationale[:300]
        if res.decision != "APPLY_ALLOWED" or not job.apply_when_allowed:
            self.save_state(st)
            return outcome
        try:
            applied = apply_fix(self.repo, job.project_dir, res.experiment_id, actor=self.actor)
        except ApplyRefusedError as exc:
            outcome.note = f"apply refused: {exc}"
            self.save_state(st)
            return outcome
        outcome.applied = True
        if not job.confirm_after_apply or not res.learning_id:
            self.save_state(st)
            return outcome
        confirm = RetrofitCycle(self.repo, actor=self.actor, seed=job.seed or 0).confirm(
            job.project_dir, job.agent, good_campaign_id=baseline, learning_id=res.learning_id
        )
        outcome.confirmed = confirm["learning_status"]
        if confirm["learning_status"] == "verified":
            st.last_good_campaign_id = str(confirm["campaign_id"])
        else:
            rollback(
                self.repo,
                job.project_dir,
                actor=self.actor,
                backup=applied.backup_path,
                reason=f"confirmation failed on DEEP campaign {confirm['campaign_id']}",
            )
            outcome.note = f"applied then rolled back: confirmation {confirm['learning_status']}"
        self.save_state(st)
        return outcome

    def _baseline(self, job: ScheduledJob, st: JobState) -> str | None:
        if job.baseline == "none":
            return None
        if job.baseline == "last_good":
            return st.last_good_campaign_id
        return job.baseline

    def _retrofit_guard(self, job: ScheduledJob, st: JobState, now: datetime) -> str | None:
        today = now.date().isoformat()
        used = st.retrofits_today if st.retrofit_day == today else 0
        if used >= job.max_retrofits_per_day:
            return f"retrofit guard: {used}/{job.max_retrofits_per_day} retrofits already today"
        if st.last_retrofit_at and now < st.last_retrofit_at + timedelta(
            minutes=job.cooldown_minutes_after_retrofit
        ):
            return f"retrofit guard: cool-down of {job.cooldown_minutes_after_retrofit} min active"
        return None

    @staticmethod
    def _count_retrofit(st: JobState, now: datetime) -> None:
        today = now.date().isoformat()
        if st.retrofit_day != today:
            st.retrofit_day, st.retrofits_today = today, 0
        st.retrofits_today += 1
        st.last_retrofit_at = now
