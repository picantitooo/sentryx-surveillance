"""Regressions for schema locks and RTSP recovery; no camera connection."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

from app.infrastructure.persistence.alerts import AlertStore
from app.domain.alerts import EventPolicy
from app.infrastructure.persistence.detections import DetectionStore


def test_concurrent_alert_open_and_disconnect(tmp_path):
    detections = DetectionStore(tmp_path / "events.db")
    alerts = AlertStore(detections.path)
    record = detections.save(dict(clase="Hurto", confianza=.9, timestamp=1,
                                 simulated=True), "cam", session_id="session")
    opening = dict(alert=dict(started=True, ended=False, threshold=.5))
    with ThreadPoolExecutor(max_workers=4) as executor:
        futures = [executor.submit(alerts.apply, opening, record) for _ in range(6)]
        futures.append(executor.submit(alerts.interrupt, "session", "source_disconnected"))
        for future in futures:
            future.result(timeout=10)
    assert alerts.list(status="active")["total"] == 0
    assert alerts.apply(opening, record) is None
    for event in alerts.list()["items"]:
        assert event["status"] == "interrupted"
        assert event["timestamp_fin"] is None

def test_schema_commits_before_writes_and_is_not_repeated(monkeypatch):
    import app.infrastructure.persistence.detections as module
    operations = []

    class Connection:
        def execute(self, statement, parameters=None):
            operations.append(statement)
            return SimpleNamespace(rowcount=0)

        def __enter__(self):
            return self

        def __exit__(self, kind, value, traceback):
            operations.append("ROLLBACK" if kind else "COMMIT")

        def close(self):
            operations.append("CLOSE")

    monkeypatch.setattr(module, "connect", lambda _: Connection())
    store = AlertStore("postgresql://unused")
    store.interrupt("s")
    update = next(i for i, value in enumerate(operations) if value.startswith("UPDATE"))
    assert operations.index("COMMIT") < operations.index("BEGIN IMMEDIATE") < update
    assert operations.index("SELECT pg_advisory_xact_lock(734821906)") < next(
        i for i, value in enumerate(operations) if value.startswith("CREATE"))
    operations.clear()
    store.interrupt("s")
    assert not any(value.startswith("CREATE") for value in operations)

@pytest.mark.parametrize("sqlstate,expected_attempts", [("40P01", 3), ("40001", 3), ("23503", 1)])
def test_transaction_retry_is_bounded_and_rolls_back(monkeypatch, sqlstate, expected_attempts):
    import app.infrastructure.persistence.alerts as module
    attempts, rollbacks, closed = [], [], []

    class Failure(Exception):
        pass

    error = Failure("database conflict")
    error.sqlstate = sqlstate

    class Connection:
        def execute(self, statement, parameters=None):
            if statement.startswith("UPDATE"):
                attempts.append(1)
                raise error

        def __enter__(self):
            return self

        def __exit__(self, kind, value, traceback):
            rollbacks.append(kind is Failure)

        def close(self):
            closed.append(1)

    store = AlertStore("unused.db")
    monkeypatch.setattr(store, "connect", Connection)
    monkeypatch.setattr(module.time, "sleep", lambda _: None)
    with pytest.raises(Failure):
        store.interrupt("s")
    assert len(attempts) == len(closed) == expected_attempts
    assert rollbacks == [True] * expected_attempts
