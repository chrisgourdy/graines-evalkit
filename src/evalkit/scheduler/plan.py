"""Schedule plan: a YAML file declaring jobs to run unattended (cron, systemd, container).

Every guard is explicit and has a safe default: a job never retrofits unless asked, never
applies a fix unless asked *and* the project policy opens the level-3 perimeter, is capped
in cost per cycle when the adapter is cost-bearing, and pauses itself after repeated
failures until a human resumes it.
"""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import Field, ValidationError, field_validator

from evalkit.contracts import ContractModel, Profile


class ScheduledJob(ContractModel):
    name: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{1,63}$")
    project_dir: Path
    agent: str
    profile: Profile = Profile.STANDARD
    interval_minutes: int = Field(default=1440, ge=1)
    seed: int | None = None
    workers: int = Field(default=1, ge=1, le=16)
    baseline: str = Field(
        default="last_good",
        description="'last_good' (tracked by the scheduler), 'none', or a campaign id.",
    )
    max_cost_per_cycle: float | None = Field(
        default=None, ge=0, description="Campaign-scope budget cap created before each run."
    )
    retrofit: bool = Field(default=False, description="Run the retrofit cycle on incidents.")
    apply_when_allowed: bool = Field(
        default=False,
        description="Apply an APPLY_ALLOWED fix to the project (level 3 perimeter required).",
    )
    confirm_after_apply: bool = Field(
        default=True,
        description="After applying, run a DEEP confirmation; roll back when it fails.",
    )
    max_retrofit_iterations: int = Field(default=2, ge=1, le=5)
    max_retrofits_per_day: int = Field(default=1, ge=0)
    cooldown_minutes_after_retrofit: int = Field(default=60, ge=0)
    max_consecutive_failures: int = Field(default=3, ge=1)

    @field_validator("profile", mode="before")
    @classmethod
    def _profile_case(cls, value: object) -> object:
        return value.upper() if isinstance(value, str) else value


class SchedulePlan(ContractModel):
    plan_id: str = Field(pattern=r"^[a-z0-9][a-z0-9._-]{1,63}$")
    jobs: list[ScheduledJob] = Field(min_length=1)

    @field_validator("jobs")
    @classmethod
    def _unique_names(cls, jobs: list[ScheduledJob]) -> list[ScheduledJob]:
        names = [j.name for j in jobs]
        if len(set(names)) != len(names):
            msg = "job names must be unique"
            raise ValueError(msg)
        return jobs


class PlanLoadError(ValueError):
    pass


def load_plan(path: Path) -> SchedulePlan:
    p = Path(path)
    if not p.is_file():
        msg = f"plan file not found: {p}"
        raise PlanLoadError(msg)
    try:
        data = yaml.safe_load(p.read_text(encoding="utf-8")) or {}
        plan = SchedulePlan.model_validate(data)
    except (ValidationError, yaml.YAMLError) as exc:
        msg = f"{p}: {exc}"
        raise PlanLoadError(msg) from exc
    # project_dir relative to the plan file, not to the cwd
    jobs = [
        j.model_copy(
            update={
                "project_dir": j.project_dir
                if j.project_dir.is_absolute()
                else (p.parent / j.project_dir).resolve()
            }
        )
        for j in plan.jobs
    ]
    return plan.model_copy(update={"jobs": jobs})
