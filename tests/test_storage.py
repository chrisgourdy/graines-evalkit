"""Storage: migrations, transactions, artifacts, append-only audit with hash chain."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from evalkit.audit import make_event
from evalkit.contracts import EventType
from evalkit.storage import NotFoundError, SQLiteRepository


def test_migrations_apply_once(tmp_path: Path) -> None:
    repo = SQLiteRepository(tmp_path)
    assert repo.applied_migrations() == []
    assert repo.migrate() == [1, 2, 3, 4]
    assert repo.migrate() == []
    assert repo.applied_migrations() == [1, 2, 3, 4]


def test_transaction_rollback(repo: SQLiteRepository) -> None:
    ev = make_event(EventType.CONFIG_CHANGED, component="test", project_id="p")
    with pytest.raises(RuntimeError), repo.transaction():
        repo.emit(ev)
        raise RuntimeError("boom")
    assert list(repo.query(project_id="p")) == []


def test_nested_transactions_commit_once(repo: SQLiteRepository) -> None:
    with repo.transaction(), repo.transaction():
        repo.emit(make_event(EventType.CONFIG_CHANGED, component="test", project_id="p"))
    assert len(list(repo.query(project_id="p"))) == 1


def test_artifact_roundtrip_content_addressed(repo: SQLiteRepository) -> None:
    ref1 = repo.put_artifact(b"hello", kind="txt")
    ref2 = repo.put_artifact(b"hello", kind="txt")
    assert ref1 == ref2
    assert ref1.startswith("sha256:")
    assert repo.get_artifact(ref1) == b"hello"
    with pytest.raises(NotFoundError):
        repo.get_artifact("sha256:" + "0" * 64 + ":txt")


def test_audit_sequence_and_chain(repo: SQLiteRepository) -> None:
    events = [
        repo.emit(make_event(EventType.CAMPAIGN_STARTED, component="test", campaign_id="c"))
        for _ in range(5)
    ]
    assert [e.sequence for e in events] == [1, 2, 3, 4, 5]
    ok, n = repo.verify_chain()
    assert ok and n == 5
    stored = list(repo.query(campaign_id="c"))
    assert [e.event_id for e in stored] == [e.event_id for e in events]


def test_audit_tamper_detected(repo: SQLiteRepository) -> None:
    repo.emit(make_event(EventType.CAMPAIGN_STARTED, component="test", campaign_id="c"))
    repo.emit(make_event(EventType.CAMPAIGN_ENDED, component="test", campaign_id="c"))
    # Tamper directly in SQL (the code base itself never updates audit rows).
    row = repo._conn.execute("SELECT json FROM audit_events WHERE sequence=1").fetchone()
    body = json.loads(row["json"])
    body["actor"] = "attacker"
    repo._conn.execute(
        "UPDATE audit_events SET json=? WHERE sequence=1", (json.dumps(body, sort_keys=True),)
    )
    ok, bad = repo.verify_chain()
    assert not ok and bad == 1


def test_correction_event_never_edits_original(repo: SQLiteRepository) -> None:
    original = repo.emit(
        make_event(EventType.USAGE_RECORDED, component="test", run_id="r", payload={"n": 1})
    )
    fix = repo.correct(original.event_id, "wrong count", {"n": 2})
    assert fix.corrects == original.event_id
    assert fix.event_type is EventType.CORRECTION
    again = next(e for e in repo.query(run_id="r") if e.event_id == original.event_id)
    assert again.payload == {"n": 1}
    ok, n = repo.verify_chain()
    assert ok and n == 2


def test_export_jsonl(repo: SQLiteRepository, tmp_path: Path) -> None:
    repo.emit(make_event(EventType.CAMPAIGN_STARTED, component="test", campaign_id="c1"))
    repo.emit(make_event(EventType.CAMPAIGN_STARTED, component="test", campaign_id="c2"))
    out = tmp_path / "audit.jsonl"
    assert repo.export_jsonl(str(out), campaign_id="c1") == 1
    assert json.loads(out.read_text().splitlines()[0])["campaign_id"] == "c1"


def test_no_update_or_delete_on_audit_table_in_code() -> None:
    src = (Path(__file__).resolve().parents[1] / "src" / "evalkit").rglob("*.py")
    for path in src:
        text = path.read_text(encoding="utf-8").upper()
        assert "UPDATE AUDIT_EVENTS" not in text, path
        assert "DELETE FROM AUDIT_EVENTS" not in text, path


def test_redaction_in_events() -> None:
    ev = make_event(
        EventType.CONFIG_CHANGED,
        component="test",
        payload={"api_key": "sk-123", "nested": {"Authorization": "Bearer x"}, "ok": 1},
    )
    assert ev.payload == {
        "api_key": "<redacted>",
        "nested": {"Authorization": "<redacted>"},
        "ok": 1,
    }
