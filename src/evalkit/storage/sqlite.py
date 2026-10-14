"""SQLite implementation of the Repository and AuditTrail ports (ADR-0002).

* WAL mode, explicit ``BEGIN IMMEDIATE`` transactions (writer lock) with nesting support.
* Numbered SQL migrations under ``storage/migrations``.
* ``audit_events`` is append-only: this module contains no UPDATE/DELETE on it, and every row
  carries a SHA-256 chained to the previous row (tamper evidence, not immutability).
* Artifacts are stored content-addressed under ``<data_dir>/artifacts``.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from importlib import resources
from pathlib import Path
from typing import Any

from evalkit.contracts import (
    AuditEvent,
    Campaign,
    EvaluationResult,
    PriceEntry,
    Run,
    Scenario,
    Scorecard,
    Ticket,
    new_id,
    utcnow,
)

GENESIS_HASH = "0" * 64


class NotFoundError(KeyError):
    """Entity not found in the repository."""


def _statements(sql: str) -> list[str]:
    body = "\n".join(line for line in sql.splitlines() if not line.lstrip().startswith("--"))
    return [s.strip() for s in body.split(";") if s.strip()]


def _canonical(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


class SQLiteRepository:
    """Repository + AuditTrail backed by one SQLite file."""

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.data_dir / "evalkit.db"
        self.artifacts_dir = self.data_dir / "artifacts"
        self.artifacts_dir.mkdir(exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, isolation_level=None, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._conn.execute("PRAGMA busy_timeout=5000")
        self._tx_depth = 0

    # ----------------------------------------------------------------- lifecycle
    def close(self) -> None:
        self._conn.close()

    @contextmanager
    def transaction(self) -> Iterator[None]:
        if self._tx_depth == 0:
            self._conn.execute("BEGIN IMMEDIATE")
        self._tx_depth += 1
        try:
            yield
        except BaseException:
            self._tx_depth -= 1
            if self._tx_depth == 0:
                self._conn.execute("ROLLBACK")
            raise
        else:
            self._tx_depth -= 1
            if self._tx_depth == 0:
                self._conn.execute("COMMIT")

    # ---------------------------------------------------------------- migrations
    @staticmethod
    def available_migrations() -> list[tuple[int, str, str]]:
        """(version, name, sql) sorted by version."""
        out: list[tuple[int, str, str]] = []
        pkg = resources.files("evalkit.storage") / "migrations"
        for entry in pkg.iterdir():
            name = entry.name
            if not name.endswith(".sql"):
                continue
            version = int(name.split("_", 1)[0])
            out.append((version, name[:-4], entry.read_text(encoding="utf-8")))
        return sorted(out)

    def applied_migrations(self) -> list[int]:
        row = self._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='schema_migrations'"
        ).fetchone()
        if row is None:
            return []
        return [
            int(r["version"])
            for r in self._conn.execute("SELECT version FROM schema_migrations ORDER BY version")
        ]

    def migrate(self) -> list[int]:
        """Apply pending migrations in order; return the versions applied."""
        applied = set(self.applied_migrations())
        done: list[int] = []
        for version, name, sql in self.available_migrations():
            if version in applied:
                continue
            with self.transaction():
                # executescript() would COMMIT implicitly: run statements one by one instead.
                for statement in _statements(sql):
                    self._conn.execute(statement)
                self._conn.execute(
                    "INSERT INTO schema_migrations(version, name, applied_at) VALUES (?, ?, ?)",
                    (version, name, utcnow().isoformat()),
                )
            done.append(version)
        return done

    # ----------------------------------------------------------------- scenarios
    def save_scenario(self, scenario: Scenario) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO scenarios(scenario_id, version, project_id, agent_id,"
            " dataset, json) VALUES (?, ?, ?, ?, ?, ?)",
            (
                scenario.scenario_id,
                scenario.version,
                scenario.project_id,
                scenario.agent_id,
                scenario.dataset.value,
                scenario.model_dump_json(),
            ),
        )

    def get_scenario(self, scenario_id: str, version: str | None = None) -> Scenario:
        if version is None:
            row = self._conn.execute(
                "SELECT json FROM scenarios WHERE scenario_id=? ORDER BY version DESC LIMIT 1",
                (scenario_id,),
            ).fetchone()
        else:
            row = self._conn.execute(
                "SELECT json FROM scenarios WHERE scenario_id=? AND version=?",
                (scenario_id, version),
            ).fetchone()
        if row is None:
            raise NotFoundError(scenario_id)
        return Scenario.model_validate_json(row["json"])

    def list_scenarios(self, project_id: str, agent_id: str | None = None) -> Iterator[Scenario]:
        if agent_id is None:
            rows = self._conn.execute(
                "SELECT json FROM scenarios WHERE project_id=? ORDER BY scenario_id, version",
                (project_id,),
            )
        else:
            rows = self._conn.execute(
                "SELECT json FROM scenarios WHERE project_id=? AND agent_id=?"
                " ORDER BY scenario_id, version",
                (project_id, agent_id),
            )
        for row in rows:
            yield Scenario.model_validate_json(row["json"])

    # ----------------------------------------------------------------- campaigns
    def save_campaign(self, campaign: Campaign) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO campaigns(campaign_id, project_id, agent_id, agent_version,"
            " status, created_at, json) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                campaign.campaign_id,
                campaign.project_id,
                campaign.agent_id,
                campaign.agent_version,
                campaign.status.value,
                campaign.created_at.isoformat(),
                campaign.model_dump_json(),
            ),
        )

    def get_campaign(self, campaign_id: str) -> Campaign:
        row = self._conn.execute(
            "SELECT json FROM campaigns WHERE campaign_id=?", (campaign_id,)
        ).fetchone()
        if row is None:
            raise NotFoundError(campaign_id)
        return Campaign.model_validate_json(row["json"])

    def list_campaigns(self, project_id: str, agent_id: str | None = None) -> Iterator[Campaign]:
        if agent_id is None:
            rows = self._conn.execute(
                "SELECT json FROM campaigns WHERE project_id=? ORDER BY created_at", (project_id,)
            )
        else:
            rows = self._conn.execute(
                "SELECT json FROM campaigns WHERE project_id=? AND agent_id=? ORDER BY created_at",
                (project_id, agent_id),
            )
        for row in rows:
            yield Campaign.model_validate_json(row["json"])

    # ---------------------------------------------------------------------- runs
    def save_run(self, run: Run) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO runs(run_id, campaign_id, scenario_id, scenario_version,"
            " attempt, status, json) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                run.run_id,
                run.campaign_id,
                run.scenario_id,
                run.scenario_version,
                run.attempt,
                run.status.value,
                run.model_dump_json(),
            ),
        )

    def list_runs(self, campaign_id: str) -> Iterator[Run]:
        rows = self._conn.execute(
            "SELECT json FROM runs WHERE campaign_id=? ORDER BY scenario_id, attempt",
            (campaign_id,),
        )
        for row in rows:
            yield Run.model_validate_json(row["json"])

    # ------------------------------------------------------------------- results
    def save_result(self, result: EvaluationResult) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO results(result_id, run_id, evaluator_id, dimension,"
            " control_state, status, json) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                result.result_id,
                result.run_id,
                result.evaluator_id,
                result.dimension.value,
                result.control_state.value,
                result.status.value,
                result.model_dump_json(),
            ),
        )

    def list_results(self, run_id: str) -> Iterator[EvaluationResult]:
        rows = self._conn.execute(
            "SELECT json FROM results WHERE run_id=? ORDER BY result_id", (run_id,)
        )
        for row in rows:
            yield EvaluationResult.model_validate_json(row["json"])

    # -------------------------------------------------------------------- prices
    def save_price(self, price: PriceEntry) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO prices(price_id, provider, model_id, valid_from, valid_to,"
            " json) VALUES (?, ?, ?, ?, ?, ?)",
            (
                price.price_id,
                price.provider,
                price.model_id,
                price.valid_from.isoformat(),
                price.valid_to.isoformat() if price.valid_to else None,
                price.model_dump_json(),
            ),
        )

    def find_price(self, provider: str, model_id: str, on: str) -> PriceEntry | None:
        row = self._conn.execute(
            "SELECT json FROM prices WHERE provider=? AND model_id=? AND valid_from<=?"
            " AND (valid_to IS NULL OR valid_to>=?) ORDER BY valid_from DESC LIMIT 1",
            (provider, model_id, on, on),
        ).fetchone()
        return PriceEntry.model_validate_json(row["json"]) if row else None

    # ---------------------------------------------------------- scorecards/tickets
    def save_scorecard(self, scorecard: Scorecard) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO scorecards(scorecard_id, campaign_id, json) VALUES (?, ?, ?)",
            (scorecard.scorecard_id, scorecard.campaign_id, scorecard.model_dump_json()),
        )

    def save_ticket(self, ticket: Ticket) -> None:
        self._conn.execute(
            "INSERT OR REPLACE INTO tickets(ticket_id, project_id, status, json)"
            " VALUES (?, ?, ?, ?)",
            (ticket.ticket_id, ticket.project_id, ticket.status.value, ticket.model_dump_json()),
        )

    def get_ticket(self, ticket_id: str) -> Ticket:
        row = self._conn.execute(
            "SELECT json FROM tickets WHERE ticket_id=?", (ticket_id,)
        ).fetchone()
        if row is None:
            raise NotFoundError(ticket_id)
        return Ticket.model_validate_json(row["json"])

    # ----------------------------------------------------------------- artifacts
    def put_artifact(self, data: bytes, *, kind: str) -> str:
        digest = hashlib.sha256(data).hexdigest()
        path = self.artifacts_dir / digest[:2] / f"{digest}.{kind}"
        path.parent.mkdir(exist_ok=True)
        if not path.exists():
            path.write_bytes(data)
        return f"sha256:{digest}:{kind}"

    def get_artifact(self, ref: str) -> bytes:
        _, digest, kind = ref.split(":", 2)
        path = self.artifacts_dir / digest[:2] / f"{digest}.{kind}"
        if not path.exists():
            raise NotFoundError(ref)
        return path.read_bytes()

    # --------------------------------------------------------------- audit trail
    def _last_hash(self) -> str:
        row = self._conn.execute(
            "SELECT hash FROM audit_events ORDER BY sequence DESC LIMIT 1"
        ).fetchone()
        return str(row["hash"]) if row else GENESIS_HASH

    def emit(self, event: AuditEvent) -> AuditEvent:
        with self.transaction():
            prev = self._last_hash()
            body = event.model_dump(mode="json", exclude={"sequence"})
            digest = hashlib.sha256(prev.encode() + _canonical(body)).hexdigest()
            cur = self._conn.execute(
                "INSERT INTO audit_events(event_id, timestamp, event_type, project_id, campaign_id,"
                " run_id, prev_hash, hash, json) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    event.event_id,
                    event.timestamp.isoformat(),
                    event.event_type.value,
                    event.project_id,
                    event.campaign_id,
                    event.run_id,
                    prev,
                    digest,
                    json.dumps(body, sort_keys=True, ensure_ascii=False),
                ),
            )
            sequence = int(cur.lastrowid or 0)
        return event.model_copy(update={"sequence": sequence})

    def correct(self, event_id: str, reason: str, payload: dict[str, object]) -> AuditEvent:
        from evalkit import __version__
        from evalkit.contracts import EventType

        original = self._conn.execute(
            "SELECT json FROM audit_events WHERE event_id=?", (event_id,)
        ).fetchone()
        if original is None:
            raise NotFoundError(event_id)
        orig = json.loads(original["json"])
        correction = AuditEvent(
            event_id=new_id("evt"),
            timestamp=utcnow(),
            event_type=EventType.CORRECTION,
            actor="system",
            component="audit",
            version=__version__,
            project_id=orig.get("project_id"),
            campaign_id=orig.get("campaign_id"),
            run_id=orig.get("run_id"),
            corrects=event_id,
            payload={"reason": reason, **payload},
        )
        return self.emit(correction)

    def query(self, **filters: str) -> Iterator[AuditEvent]:
        allowed = {"project_id", "campaign_id", "run_id", "event_type"}
        clauses = [f"{k}=?" for k in filters if k in allowed]
        params = [v for k, v in filters.items() if k in allowed]
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""
        rows = self._conn.execute(
            f"SELECT sequence, json FROM audit_events{where} ORDER BY sequence",  # noqa: S608
            params,
        )
        for row in rows:
            event = AuditEvent.model_validate_json(row["json"])
            yield event.model_copy(update={"sequence": int(row["sequence"])})

    def export_jsonl(self, path: str, **filters: str) -> int:
        count = 0
        with Path(path).open("w", encoding="utf-8") as fh:
            for event in self.query(**filters):
                fh.write(event.model_dump_json() + "\n")
                count += 1
        return count

    def verify_chain(self) -> tuple[bool, int]:
        """Recompute the hash chain. Returns (ok, first_bad_sequence_or_count)."""
        prev = GENESIS_HASH
        checked = 0
        for row in self._conn.execute(
            "SELECT sequence, prev_hash, hash, json FROM audit_events ORDER BY sequence"
        ):
            body = json.loads(row["json"])
            expected = hashlib.sha256(prev.encode() + _canonical(body)).hexdigest()
            if row["prev_hash"] != prev or row["hash"] != expected:
                return False, int(row["sequence"])
            prev = str(row["hash"])
            checked += 1
        return True, checked
