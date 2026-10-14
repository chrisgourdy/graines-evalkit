"""Controlled application of a validated fix to a real project (level 3, EK-0033).

Applying means rewriting the agent entry of ``evalkit.yaml``. It is refused unless the project
policy allows ``apply_fix_low_risk`` for this actor (never an ``agent:*`` actor), the fix
comes from a recorded experiment whose decision was ``APPLY_ALLOWED``, and the project loads
after the change. A timestamped backup of the previous file is kept under
``<project>/.evalkit-backups/`` and ``rollback`` restores it; both are audit events.
"""

from __future__ import annotations

import hashlib
import json
import shutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from evalkit.audit import make_event
from evalkit.contracts import AutonomyLevel, EventType, Severity, utcnow
from evalkit.core.project import load_project, load_scenarios
from evalkit.governance import Action, ProjectPolicyEngine
from evalkit.storage.sqlite import SQLiteRepository

BACKUP_DIR = ".evalkit-backups"


class ApplyRefusedError(RuntimeError):
    """The fix cannot be applied under the project's policy or the recorded evidence."""


@dataclass
class AppliedFix:
    experiment_id: str
    agent_id: str
    backup_path: Path
    before: dict[str, Any]
    after: dict[str, Any]


def get_experiment(repo: SQLiteRepository, experiment_id: str) -> dict[str, Any]:
    row = repo._conn.execute(
        "SELECT experiment_id, project_id, agent_id, ticket_id, status, json FROM experiments"
        " WHERE experiment_id=?",
        (experiment_id,),
    ).fetchone()
    if row is None:
        from evalkit.storage import NotFoundError

        raise NotFoundError(experiment_id)
    data = dict(json.loads(row["json"]))
    data.update(
        {
            "experiment_id": row["experiment_id"],
            "project_id": row["project_id"],
            "agent_id": row["agent_id"],
            "ticket_id": row["ticket_id"],
            "decision": row["status"],
        }
    )
    return data


def list_backups(project_dir: Path) -> list[Path]:
    root = Path(project_dir) / BACKUP_DIR
    return sorted(root.glob("evalkit.yaml.*.bak")) if root.is_dir() else []


def apply_fix(
    repo: SQLiteRepository,
    project_dir: Path,
    experiment_id: str,
    *,
    actor: str,
) -> AppliedFix:
    exp = get_experiment(repo, experiment_id)
    config = load_project(project_dir)
    if config.project_id != exp["project_id"]:
        msg = f"experiment belongs to project {exp['project_id']!r}, not {config.project_id!r}"
        raise ApplyRefusedError(msg)
    if exp["decision"] != "APPLY_ALLOWED":
        msg = f"experiment decision is {exp['decision']}: only APPLY_ALLOWED fixes can be applied"
        raise ApplyRefusedError(msg)
    fix = exp.get("fix")
    if not isinstance(fix, dict):
        msg = "experiment carries no fix"
        raise ApplyRefusedError(msg)
    agent_id = str(exp["agent_id"])
    verdict = ProjectPolicyEngine(config.autonomy).decide(
        Action(
            kind="apply_fix_low_risk",
            target=agent_id,
            actor=actor,
            required_level=AutonomyLevel.CONTROLLED_APPLY,
            details={"experiment_id": experiment_id},
        )
    )
    if not verdict.allowed:
        raise ApplyRefusedError(verdict.reason)
    path = Path(project_dir) / "evalkit.yaml"
    raw = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    before = dict(raw["agents"].get(agent_id, {}))
    if before == fix:
        msg = "project already carries this configuration: nothing to apply"
        raise ApplyRefusedError(msg)
    backup_root = Path(project_dir) / BACKUP_DIR
    backup_root.mkdir(exist_ok=True)
    backup = backup_root / f"evalkit.yaml.{utcnow():%Y%m%dT%H%M%S%f}.bak"
    shutil.copy2(path, backup)
    raw["agents"][agent_id] = fix
    path.write_text(yaml.safe_dump(raw, sort_keys=False), encoding="utf-8")
    try:
        load_scenarios(project_dir, load_project(project_dir))
    except Exception:
        shutil.copy2(backup, path)  # never leave a broken project behind
        raise
    repo.emit(
        make_event(
            EventType.CONFIG_CHANGED,
            component="improvement",
            actor=actor,
            severity=Severity.WARNING,
            project_id=config.project_id,
            agent_id=agent_id,
            payload={
                "action": "fix.applied",
                "experiment_id": experiment_id,
                "ticket_id": exp.get("ticket_id"),
                "backup": str(backup),
                "before": before,
                "after": fix,
                "policy": verdict.reason,
            },
        )
    )
    return AppliedFix(experiment_id, agent_id, backup, before, fix)


def rollback(
    repo: SQLiteRepository,
    project_dir: Path,
    *,
    actor: str,
    backup: Path | None = None,
    reason: str = "manual rollback",
) -> Path:
    """Restore ``evalkit.yaml`` from the latest (or given) backup; the backup file is kept."""
    candidates = list_backups(project_dir)
    chosen = Path(backup) if backup else (candidates[-1] if candidates else None)
    if chosen is None or not chosen.is_file():
        msg = f"no backup to roll back to under {Path(project_dir) / BACKUP_DIR}"
        raise ApplyRefusedError(msg)
    path = Path(project_dir) / "evalkit.yaml"
    current = path.read_text(encoding="utf-8")
    shutil.copy2(chosen, path)
    config = load_project(project_dir)
    repo.emit(
        make_event(
            EventType.CONFIG_CHANGED,
            component="improvement",
            actor=actor,
            severity=Severity.WARNING,
            project_id=config.project_id,
            payload={
                "action": "fix.rolled_back",
                "restored_from": str(chosen),
                "reason": reason,
                "replaced_config_sha256": hashlib.sha256(current.encode()).hexdigest(),
            },
        )
    )
    return chosen
