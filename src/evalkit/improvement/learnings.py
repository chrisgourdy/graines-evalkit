"""Portable knowledge base: each learning carries provenance (evidence ids) and a validation
status ``observed`` → ``verified`` → ``adopted`` | ``rejected``. Never a rule before ``adopted``."""

from __future__ import annotations

import json
from typing import Any

from evalkit.audit import make_event
from evalkit.contracts import EventType, new_id, utcnow
from evalkit.storage.sqlite import SQLiteRepository

STATUSES = ("observed", "verified", "adopted", "rejected")


class LearningStore:
    def __init__(self, repo: SQLiteRepository, *, actor: str = "system") -> None:
        self.repo = repo
        self.actor = actor

    def record(
        self,
        *,
        project_id: str,
        scope: str,
        statement: str,
        evidence_refs: list[str],
        status: str = "observed",
    ) -> dict[str, Any]:
        if status not in STATUSES:
            msg = f"unknown learning status {status!r}"
            raise ValueError(msg)
        now = utcnow().isoformat()
        learning = {
            "learning_id": new_id("lrn"),
            "created_at": now,
            "updated_at": now,
            "project_id": project_id,
            "scope": scope,
            "statement": statement,
            "evidence_refs": evidence_refs,
            "status": status,
            "history": [f"{now} {status} by {self.actor}"],
        }
        with self.repo.transaction():
            self.repo._conn.execute(
                "INSERT INTO learnings(learning_id, created_at, updated_at, project_id, scope, status, json) VALUES (?,?,?,?,?,?,?)",
                (
                    learning["learning_id"],
                    now,
                    now,
                    project_id,
                    scope,
                    status,
                    json.dumps(learning, sort_keys=True),
                ),
            )
        self.repo.emit(
            make_event(
                EventType.CONFIG_CHANGED,
                component="improvement",
                actor=self.actor,
                project_id=project_id,
                payload={"learning_id": learning["learning_id"], "status": status, "scope": scope},
            )
        )
        return learning

    def get(self, learning_id: str) -> dict[str, Any]:
        row = self.repo._conn.execute(
            "SELECT json FROM learnings WHERE learning_id=?", (learning_id,)
        ).fetchone()
        if row is None:
            from evalkit.storage import NotFoundError

            raise NotFoundError(learning_id)
        return dict(json.loads(row["json"]))

    def set_status(
        self, learning_id: str, status: str, *, evidence_refs: list[str] | None = None
    ) -> dict[str, Any]:
        if status not in STATUSES:
            msg = f"unknown learning status {status!r}"
            raise ValueError(msg)
        learning = self.get(learning_id)
        now = utcnow().isoformat()
        learning["status"] = status
        learning["updated_at"] = now
        learning["evidence_refs"] = list(
            dict.fromkeys([*learning["evidence_refs"], *(evidence_refs or [])])
        )
        learning["history"].append(f"{now} {status} by {self.actor}")
        with self.repo.transaction():
            self.repo._conn.execute(
                "UPDATE learnings SET updated_at=?, status=?, json=? WHERE learning_id=?",
                (now, status, json.dumps(learning, sort_keys=True), learning_id),
            )
        self.repo.emit(
            make_event(
                EventType.VALIDATION_DECISION,
                component="improvement",
                actor=self.actor,
                project_id=learning["project_id"],
                payload={"learning_id": learning_id, "status": status},
            )
        )
        return learning

    def list(self, project_id: str, status: str | None = None) -> list[dict[str, Any]]:
        if status:
            rows = self.repo._conn.execute(
                "SELECT json FROM learnings WHERE project_id=? AND status=? ORDER BY created_at",
                (project_id, status),
            ).fetchall()
        else:
            rows = self.repo._conn.execute(
                "SELECT json FROM learnings WHERE project_id=? ORDER BY created_at", (project_id,)
            ).fetchall()
        return [dict(json.loads(r["json"])) for r in rows]

    def render_markdown(self, project_id: str) -> str:
        items = self.list(project_id)
        lines = [
            f"# Learnings — project {project_id}",
            "",
            "Generated from the knowledge base. Status: observed → verified → adopted | rejected. "
            "Nothing here is a rule until adopted.",
            "",
            "| id | status | scope | statement | evidence | updated |",
            "|---|---|---|---|---|---|",
        ]
        for it in items:
            lines.append(
                f"| {it['learning_id']} | {it['status']} | {it['scope']} | {it['statement']} | {', '.join(it['evidence_refs'][:6])} | {it['updated_at'][:10]} |"
            )
        return "\n".join(lines) + "\n"
