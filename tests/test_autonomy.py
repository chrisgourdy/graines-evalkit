"""Phase 7 — resume after interruption, backup/restore, controlled apply/rollback, scheduler.

Acceptance scenarios 26 (unattended execution), 27 (resume after interruption) and the restore
procedure, on simulated agents only.
"""

from __future__ import annotations

import asyncio
import shutil
import sqlite3
from collections import Counter
from datetime import timedelta
from pathlib import Path

import pytest
import yaml
from typer.testing import CliRunner

from evalkit.cli.main import app
from evalkit.contracts import CampaignStatus, EventType, Profile, RunStatus, utcnow
from evalkit.core import CampaignRefusedError, CampaignRunner
from evalkit.improvement import (
    ApplyRefusedError,
    RetrofitCycle,
    apply_fix,
    get_experiment,
    list_backups,
    rollback,
)
from evalkit.scheduler import (
    PlanLoadError,
    SchedulePlan,
    Scheduler,
    SchedulerLock,
    SchedulerLockedError,
    load_plan,
)
from evalkit.storage import SQLiteRepository

runner_cli = CliRunner()

BROKEN_GREETER = {
    "adapter": "sim.deterministic",
    "version": "1.1.0-broken",
    "params": {"behavior": "wrong"},
}


def _run(
    repo: SQLiteRepository,
    project: Path,
    agent: str,
    profile: Profile = Profile.STANDARD,
    **kw: object,
):  # type: ignore[no-untyped-def]
    runner = CampaignRunner(repo)
    return asyncio.run(runner.execute(runner.plan(project, agent, profile=profile, seed=1, **kw)))  # type: ignore[arg-type]


def _set_agent(project: Path, agent: str, config: dict[str, object]) -> None:
    path = project / "evalkit.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["agents"][agent] = config
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def _set_autonomy(project: Path, max_level: int, perimeter: list[str]) -> None:
    path = project / "evalkit.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    data["autonomy"] = {"max_level": max_level, "apply_perimeter": perimeter}
    path.write_text(yaml.safe_dump(data, sort_keys=False), encoding="utf-8")


def _agent_cfg(project: Path, agent: str) -> dict[str, object]:
    return dict(
        yaml.safe_load((project / "evalkit.yaml").read_text(encoding="utf-8"))["agents"][agent]
    )


@pytest.fixture
def project(tmp_path: Path, demo_dir: Path) -> Path:
    dst = tmp_path / "proj"
    shutil.copytree(demo_dir, dst)
    return dst


def _simulate_crash(repo: SQLiteRepository, campaign_id: str) -> tuple[str, str]:
    """Leave the campaign RUNNING: last scenario's runs gone, one run of another stuck RUNNING."""
    runs = list(repo.list_runs(campaign_id))
    victim = sorted({r.scenario_id for r in runs})[-1]
    with repo.transaction():
        repo._conn.execute(
            "DELETE FROM results WHERE run_id IN (SELECT run_id FROM runs WHERE campaign_id=? AND scenario_id=?)",
            (campaign_id, victim),
        )
        repo._conn.execute(
            "DELETE FROM runs WHERE campaign_id=? AND scenario_id=?", (campaign_id, victim)
        )
        stuck = next(r for r in runs if r.scenario_id != victim)
        repo.save_run(stuck.model_copy(update={"status": RunStatus.RUNNING, "ended_at": None}))
        camp = repo.get_campaign(campaign_id)
        repo.save_campaign(
            camp.model_copy(update={"status": CampaignStatus.RUNNING, "ended_at": None})
        )
    return victim, stuck.scenario_id


# --- resume (scenario 27) -------------------------------------------------------------------


def test_resume_completes_interrupted_campaign(repo: SQLiteRepository, project: Path) -> None:
    done = _run(repo, project, "greeter-flaky", Profile.DEEP)
    planned_total = sum(1 for _ in repo.list_runs(done.campaign_id))
    victim, stuck = _simulate_crash(repo, done.campaign_id)
    runner = CampaignRunner(repo, actor="human")
    planned = runner.resume(project, done.campaign_id)
    assert planned.resumed and planned.planned_runs == 4  # 3 lost attempts + 1 interrupted
    assert {s.scenario_id for s in planned.scenarios} == {victim, stuck}
    assert planned.repetitions == {victim: 3, stuck: 1}
    assert any("resumed:" in r for r in planned.rules)
    campaign = asyncio.run(runner.execute(planned))
    assert campaign.status is CampaignStatus.COMPLETED
    runs = list(repo.list_runs(done.campaign_id))
    assert len(runs) == planned_total + 1, "one cancelled run + all planned attempts"
    cancelled = [r for r in runs if r.status is RunStatus.CANCELLED]
    assert len(cancelled) == 1 and cancelled[0].error is None, "never counted as agent error"
    assert sum(1 for r in runs if r.status is RunStatus.RUNNING) == 0
    assert cancelled[0].scenario_id == stuck
    redone = [r for r in runs if r.scenario_id == stuck and r.attempt > 3]
    assert len(redone) == 1 and redone[0].status is RunStatus.COMPLETED and redone[0].seed
    per_scenario = Counter(r.scenario_id for r in runs if r.status is not RunStatus.CANCELLED)
    assert len(set(per_scenario.values())) == 1, "every scenario has the same attempt count"
    attempts = sorted(r.attempt for r in runs if r.scenario_id == victim)
    assert attempts == [1, 2, 3], "lost attempts are redone under their original numbers"
    events = list(repo.query(campaign_id=done.campaign_id))
    assert any(e.payload.get("action") == "campaign.resume" for e in events)
    assert any(
        e.event_type is EventType.CAMPAIGN_STARTED and e.payload.get("resumed") for e in events
    )
    ok, _n = repo.verify_chain()
    assert ok


def test_resume_refuses_completed_or_changed_campaign(
    repo: SQLiteRepository, project: Path
) -> None:
    done = _run(repo, project, "greeter")
    with pytest.raises(CampaignRefusedError, match="only RUNNING/FAILED"):
        CampaignRunner(repo).resume(project, done.campaign_id)
    _simulate_crash(repo, done.campaign_id)
    _set_agent(project, "greeter", BROKEN_GREETER)
    with pytest.raises(CampaignRefusedError, match="agent version changed"):
        CampaignRunner(repo).resume(project, done.campaign_id)


# --- backup / restore ---------------------------------------------------------------------


def test_backup_and_restore_keep_chain(
    repo: SQLiteRepository, project: Path, tmp_path: Path
) -> None:
    _run(repo, project, "greeter")
    manifest = repo.backup(tmp_path / "bk")
    assert manifest["audit_chain_ok"] and (tmp_path / "bk" / "evalkit.db").is_file()
    assert (tmp_path / "bk" / "manifest.json").is_file()
    events_at_backup = int(manifest["audit_events"])  # type: ignore[arg-type]
    _run(repo, project, "greeter")  # more events after the backup
    assert repo.verify_chain()[1] > events_at_backup
    repo.close()
    restored = SQLiteRepository.restore(tmp_path / "bk", repo.data_dir)
    ok, n = restored.verify_chain()
    assert ok and n == events_at_backup + 1  # + the restore event itself
    assert any(e.payload.get("action") == "db.restore" for e in restored.query())
    restored.close()


def test_restore_refuses_corrupt_backup(tmp_path: Path) -> None:
    bad = tmp_path / "bad"
    bad.mkdir()
    (bad / "evalkit.db").write_bytes(b"not a database at all")
    with pytest.raises((RuntimeError, sqlite3.DatabaseError)):
        SQLiteRepository.restore(bad, tmp_path / "data")
    with pytest.raises(FileNotFoundError):
        SQLiteRepository.restore(tmp_path / "missing", tmp_path / "data2")


# --- controlled apply / rollback (EK-0033) ------------------------------------------------


@pytest.fixture
def allowed_experiment(repo: SQLiteRepository, project: Path) -> str:
    _set_autonomy(project, 3, ["apply_fix_low_risk"])
    good = _run(repo, project, "greeter")
    _set_agent(project, "greeter", BROKEN_GREETER)
    broken = _run(repo, project, "greeter", baseline_campaign_id=good.campaign_id)
    res = RetrofitCycle(repo, actor="test").run(
        project, "greeter", broken_campaign_id=broken.campaign_id, good_campaign_id=good.campaign_id
    )
    assert res.decision == "APPLY_ALLOWED"
    return res.experiment_id


def test_apply_then_rollback(
    repo: SQLiteRepository, project: Path, allowed_experiment: str
) -> None:
    assert _agent_cfg(project, "greeter")["params"] == {"behavior": "wrong"}
    done = apply_fix(repo, project, allowed_experiment, actor="human")
    assert done.backup_path.is_file() and list_backups(project) == [done.backup_path]
    assert _agent_cfg(project, "greeter")["params"]["behavior"] == "reference"
    assert any(e.payload.get("action") == "fix.applied" for e in repo.query(project_id="demo"))
    with pytest.raises(ApplyRefusedError, match="nothing to apply"):
        apply_fix(repo, project, allowed_experiment, actor="human")
    restored = rollback(repo, project, actor="human", reason="test")
    assert restored == done.backup_path
    assert _agent_cfg(project, "greeter")["params"] == {"behavior": "wrong"}
    assert any(e.payload.get("action") == "fix.rolled_back" for e in repo.query(project_id="demo"))


def test_apply_refused_outside_policy(
    repo: SQLiteRepository, project: Path, allowed_experiment: str
) -> None:
    with pytest.raises(ApplyRefusedError, match="never apply"):
        apply_fix(repo, project, allowed_experiment, actor="agent:greeter")
    _set_autonomy(project, 2, [])
    with pytest.raises(ApplyRefusedError, match="max_level"):
        apply_fix(repo, project, allowed_experiment, actor="human")
    assert _agent_cfg(project, "greeter")["params"] == {"behavior": "wrong"}
    exp = get_experiment(repo, allowed_experiment)
    assert exp["decision"] == "APPLY_ALLOWED" and exp["fix"]["version"] == "1.0.0"
    with pytest.raises(ApplyRefusedError, match="no backup"):
        rollback(repo, project, actor="human")


def test_apply_refused_when_decision_not_allowed(repo: SQLiteRepository, project: Path) -> None:
    good = _run(repo, project, "greeter")
    _set_agent(project, "greeter", BROKEN_GREETER)
    broken = _run(repo, project, "greeter", baseline_campaign_id=good.campaign_id)
    res = RetrofitCycle(repo, actor="test").run(
        project, "greeter", broken_campaign_id=broken.campaign_id, good_campaign_id=good.campaign_id
    )
    assert res.decision == "HUMAN_VALIDATION_REQUIRED"
    _set_autonomy(project, 3, ["apply_fix_low_risk"])  # even if the policy opens later
    with pytest.raises(ApplyRefusedError, match="only APPLY_ALLOWED"):
        apply_fix(repo, project, res.experiment_id, actor="human")


# --- scheduler (scenario 26) --------------------------------------------------------------


def _plan(project: Path, **job: object) -> SchedulePlan:
    base = {
        "name": "greeter-std",
        "project_dir": project,
        "agent": "greeter",
        "interval_minutes": 60,
        "cooldown_minutes_after_retrofit": 0,
    }
    base.update(job)
    return SchedulePlan.model_validate({"plan_id": "test", "jobs": [base]})


def test_scheduler_runs_due_jobs_and_tracks_last_good(
    repo: SQLiteRepository, project: Path
) -> None:
    sched = Scheduler(repo, _plan(project))
    out = sched.tick()
    assert out[0].action == "ran" and out[0].scorecard_status == "PASS"
    st = sched.state(sched.plan.jobs[0])
    assert st.last_good_campaign_id == out[0].campaign_id and st.running_campaign_id is None
    assert sched.tick()[0].action == "skipped_not_due"
    later = utcnow() + timedelta(minutes=61)
    out2 = sched.tick(later)
    assert out2[0].action == "ran"
    camp = repo.get_campaign(out2[0].campaign_id or "")
    assert camp.baseline_campaign_id == out[0].campaign_id, "last good is the baseline"


def test_scheduler_unattended_retrofit_apply_confirm(repo: SQLiteRepository, project: Path) -> None:
    _set_autonomy(project, 3, ["apply_fix_low_risk"])
    sched = Scheduler(
        repo, _plan(project, retrofit=True, apply_when_allowed=True, confirm_after_apply=True)
    )
    first = sched.tick()[0]
    assert first.scorecard_status == "PASS"
    _set_agent(project, "greeter", BROKEN_GREETER)
    out = sched.tick(utcnow() + timedelta(hours=2))[0]
    assert out.scorecard_status == "FAIL"
    assert out.retrofit_decision == "APPLY_ALLOWED" and out.applied
    assert out.confirmed == "verified"
    assert _agent_cfg(project, "greeter")["params"]["behavior"] == "reference"
    assert list_backups(project)
    st = sched.state(sched.plan.jobs[0])
    assert st.retrofits_today == 1 and st.last_good_campaign_id not in (None, first.campaign_id)
    # guard: one retrofit per day by default → the next incident is only reported
    _set_agent(project, "greeter", BROKEN_GREETER)
    out3 = sched.tick(utcnow() + timedelta(hours=4))[0]
    assert out3.scorecard_status == "FAIL" and out3.retrofit_decision is None
    assert "retrofit guard" in out3.note
    assert _agent_cfg(project, "greeter")["params"] == {"behavior": "wrong"}, "untouched"


def test_scheduler_never_applies_without_perimeter(repo: SQLiteRepository, project: Path) -> None:
    sched = Scheduler(repo, _plan(project, retrofit=True, apply_when_allowed=True))
    sched.tick()
    _set_agent(project, "greeter", BROKEN_GREETER)
    out = sched.tick(utcnow() + timedelta(hours=2))[0]
    assert out.retrofit_decision == "HUMAN_VALIDATION_REQUIRED" and not out.applied
    assert _agent_cfg(project, "greeter")["params"] == {"behavior": "wrong"}


def test_scheduler_failure_guard_pauses_job_until_human(
    repo: SQLiteRepository, project: Path
) -> None:
    sched = Scheduler(repo, _plan(project, agent="ghost", max_consecutive_failures=2))
    assert sched.tick()[0].action == "failed"
    assert not sched.state(sched.plan.jobs[0]).is_paused()
    assert sched.tick(utcnow() + timedelta(hours=2))[0].action == "failed"
    st = sched.state(sched.plan.jobs[0])
    assert st.is_paused() and "2 consecutive failures" in (st.paused_reason or "")
    assert sched.tick(utcnow() + timedelta(hours=4))[0].action == "skipped_paused"
    kinds = [e for e in repo.query() if e.payload.get("action") == "schedule.job_paused"]
    assert kinds and kinds[0].event_type is EventType.HUMAN_INTERVENTION
    sched.resume_job("greeter-std", note="agent fixed")
    assert not sched.state(sched.plan.jobs[0]).is_paused()


def test_scheduler_resumes_interrupted_campaign(repo: SQLiteRepository, project: Path) -> None:
    sched = Scheduler(repo, _plan(project, agent="greeter-flaky", profile="deep", seed=4))
    first = sched.tick()[0]
    assert first.action == "ran"
    _simulate_crash(repo, first.campaign_id or "")
    st = sched.state(sched.plan.jobs[0])
    st.running_campaign_id = first.campaign_id  # what a crash mid-execute leaves behind
    sched.save_state(st)
    out = sched.tick()[0]  # due immediately: a running campaign is always due
    assert out.action == "resumed" and out.campaign_id == first.campaign_id
    assert repo.get_campaign(first.campaign_id or "").status is CampaignStatus.COMPLETED
    assert sched.state(sched.plan.jobs[0]).running_campaign_id is None


def test_scheduler_lock_is_exclusive(tmp_path: Path) -> None:
    with SchedulerLock(tmp_path), pytest.raises(SchedulerLockedError), SchedulerLock(tmp_path):
        pass
    (tmp_path / "scheduler.lock").write_text("999999")  # stale: no such process
    with SchedulerLock(tmp_path):
        assert (tmp_path / "scheduler.lock").read_text().strip().isdigit()
    assert not (tmp_path / "scheduler.lock").exists()


def test_plan_loading(tmp_path: Path, project: Path) -> None:
    plan = tmp_path / "plan.yaml"
    plan.write_text(
        "plan_id: nightly\njobs:\n  - name: aa\n    project_dir: proj\n    agent: greeter\n"
        "    profile: standard\n  - name: bb\n    project_dir: proj\n    agent: greeter-flaky\n"
        "    profile: quick\n    max_cost_per_cycle: 0.5\n",
        encoding="utf-8",
    )
    loaded = load_plan(plan)
    assert loaded.jobs[0].project_dir == (tmp_path / "proj").resolve()
    assert loaded.jobs[1].profile is Profile.QUICK and loaded.jobs[1].max_cost_per_cycle == 0.5
    assert loaded.jobs[0].retrofit is False and loaded.jobs[0].apply_when_allowed is False
    plan.write_text(
        "plan_id: x\njobs:\n  - name: aa\n    project_dir: p\n    agent: g\n  - name: aa\n    project_dir: p\n    agent: g\n"
    )
    with pytest.raises(PlanLoadError, match="unique"):
        load_plan(plan)


# --- CLI -----------------------------------------------------------------------------------


def test_cli_phase7_commands(tmp_path: Path, project: Path) -> None:
    data = tmp_path / "data"
    d = ["--data-dir", str(data)]
    _set_autonomy(project, 3, ["apply_fix_low_risk"])
    plan = tmp_path / "plan.yaml"
    plan.write_text(
        f"plan_id: nightly\njobs:\n  - name: job\n    project_dir: {project}\n    agent: greeter\n"
        "    interval_minutes: 1\n    retrofit: true\n    apply_when_allowed: true\n"
        "    cooldown_minutes_after_retrofit: 0\n",
        encoding="utf-8",
    )
    r = runner_cli.invoke(app, ["schedule", "run", str(plan), "--once", *d])
    assert r.exit_code == 0 and "scorecard=PASS" in r.output, r.output
    r = runner_cli.invoke(app, ["schedule", "status", str(plan), *d])
    assert r.exit_code == 0 and "active" in r.output
    # resume a campaign interrupted by a crash
    repo = SQLiteRepository(data)
    camp = next(iter(repo.list_campaigns("demo")))
    _simulate_crash(repo, camp.campaign_id)
    repo.close()
    r = runner_cli.invoke(
        app, ["campaign", "resume", camp.campaign_id, "--project-dir", str(project), *d]
    )
    assert r.exit_code == 0 and "status: COMPLETED" in r.output, r.output
    r = runner_cli.invoke(
        app, ["campaign", "resume", camp.campaign_id, "--project-dir", str(project), *d]
    )
    assert r.exit_code == 2
    # backup / restore
    r = runner_cli.invoke(app, ["db", "backup", str(tmp_path / "bk"), *d])
    assert r.exit_code == 0 and (tmp_path / "bk" / "manifest.json").is_file()
    r = runner_cli.invoke(app, ["db", "restore", str(tmp_path / "bk"), *d])
    assert r.exit_code == 2  # needs --yes
    r = runner_cli.invoke(app, ["db", "restore", str(tmp_path / "bk"), "--yes", *d])
    assert r.exit_code == 0 and "audit chain OK" in r.output, r.output
    # apply / rollback through the CLI on a scheduler-produced experiment
    _set_agent(project, "greeter", BROKEN_GREETER)
    repo = SQLiteRepository(data)
    repo.migrate()
    with repo.transaction():
        repo._conn.execute("UPDATE schedule_state SET last_run_at='2020-01-01T00:00:00+00:00'")
    repo.close()
    r = runner_cli.invoke(app, ["schedule", "run", str(plan), "--once", *d])
    assert "retrofit=APPLY_ALLOWED applied" in r.output, r.output
    r = runner_cli.invoke(app, ["retrofit", "rollback", "--project-dir", str(project), *d])
    assert r.exit_code == 0 and _agent_cfg(project, "greeter")["params"] == {"behavior": "wrong"}
    repo = SQLiteRepository(data)
    exp = repo._conn.execute(
        "SELECT experiment_id FROM experiments WHERE status='APPLY_ALLOWED'"
    ).fetchone()
    repo.close()
    r = runner_cli.invoke(app, ["retrofit", "apply", exp[0], "--project-dir", str(project), *d])
    assert r.exit_code == 0 and _agent_cfg(project, "greeter")["params"]["behavior"] == "reference"
    r = runner_cli.invoke(
        app, ["retrofit", "apply", exp[0], "--project-dir", str(project), "--actor", "agent:x", *d]
    )
    assert r.exit_code == 2
