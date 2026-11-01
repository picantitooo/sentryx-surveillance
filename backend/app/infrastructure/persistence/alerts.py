"""Transactional alert persistence and recovery."""
from datetime import datetime, timezone
from uuid import uuid4
import time
from functools import wraps
from app.domain.alerts import DEFAULT_THRESHOLDS
from app.infrastructure.persistence.detections import DetectionStore

def _retry_transaction(operation):
    @wraps(operation)
    def run(*args, **kwargs):
        for attempt in range(3):
            try:
                return operation(*args, **kwargs)
            except Exception as exc:
                if getattr(exc, "sqlstate", None) not in ("40P01", "40001") or attempt == 2:
                    raise
                # The operation has rolled back and closed its connection.
                time.sleep(.05 * (attempt + 1))
    return run

class AlertStore(DetectionStore):
    def _create_schema(self, connection):
        super()._create_schema(connection)
        connection.execute("""CREATE TABLE IF NOT EXISTS alerts (
            id TEXT PRIMARY KEY, detection_id TEXT NOT NULL REFERENCES detections(id),
            end_detection_id TEXT REFERENCES detections(id), camera TEXT NOT NULL,
            session_id TEXT NOT NULL, clase TEXT NOT NULL, confianza REAL NOT NULL,
            threshold REAL NOT NULL, timestamp REAL NOT NULL, fecha_hora TEXT NOT NULL,
            timestamp_inicio REAL NOT NULL, timestamp_fin REAL, fecha_hora_fin TEXT,
            duracion_segundos REAL, status TEXT NOT NULL, interruption_reason TEXT,
            UNIQUE(detection_id)
        )""")
        connection.execute("CREATE UNIQUE INDEX IF NOT EXISTS active_session ON alerts(session_id) WHERE status = 'active'")
        connection.execute("CREATE TABLE IF NOT EXISTS closed_alert_sessions (session_id TEXT PRIMARY KEY)")

    @staticmethod
    def now():
        return datetime.now(timezone.utc).isoformat()

    @_retry_transaction
    def apply(self, result, detection):
        state = result["alert"]
        connection = self.connect()
        try:
            with connection:
                connection.execute("BEGIN IMMEDIATE")
                if connection.execute("SELECT 1 FROM closed_alert_sessions WHERE session_id=?",
                                      (detection["session_id"],)).fetchone():
                    return None
                active = connection.execute("SELECT * FROM alerts WHERE session_id = ? AND status = 'active'",
                                            (detection["session_id"],)).fetchone()
                if state["started"] and active is None:
                    if detection["clase"] not in DEFAULT_THRESHOLDS or detection["confianza"] < state["threshold"]:
                        raise ValueError("La detección no cumple el threshold")
                    identifier = str(uuid4())
                    connection.execute("""INSERT OR IGNORE INTO alerts
                        (id, detection_id, camera, session_id, clase, confianza, threshold, timestamp,
                         fecha_hora, timestamp_inicio, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active')""",
                        (identifier, detection["id"], detection["camera"], detection["session_id"],
                         detection["clase"], detection["confianza"], state["threshold"], detection["timestamp"],
                         detection["fecha_hora"], detection["timestamp"]))
                    active = connection.execute("SELECT * FROM alerts WHERE detection_id = ?", (detection["id"],)).fetchone()
                if state["ended"] and active is not None:
                    if detection["clase"] != "Normal" or detection["timestamp"] < active["timestamp_inicio"]:
                        raise ValueError("Cierre de evento inválido")
                    connection.execute("""UPDATE alerts SET status='closed', end_detection_id=?, timestamp_fin=?,
                        fecha_hora_fin=?, duracion_segundos=? WHERE id=?""",
                        (detection["id"], detection["timestamp"], detection["fecha_hora"],
                         detection["timestamp"]-active["timestamp_inicio"], active["id"]))
                    active = connection.execute("SELECT * FROM alerts WHERE id=?", (active["id"],)).fetchone()
                return dict(active) if active is not None else None
        finally:
            connection.close()

    @_retry_transaction
    def interrupt(self, session_id=None, reason="service_restarted"):
        connection = self.connect()
        try:
            with connection:
                connection.execute("BEGIN IMMEDIATE")
                if session_id is not None and reason == "source_disconnected":
                    connection.execute("INSERT OR IGNORE INTO closed_alert_sessions VALUES (?)", (session_id,))
                cursor = connection.execute("UPDATE alerts SET status='interrupted', interruption_reason=?, fecha_hora_fin=?"
                    " WHERE status='active'" + (" AND session_id=?" if session_id is not None else ""),
                    (reason, self.now(), session_id) if session_id is not None else (reason, self.now()))
                return cursor.rowcount
        finally:
            connection.close()

    def get(self, identifier):
        connection = self.connect()
        try:
            row = connection.execute("SELECT * FROM alerts WHERE id=?", (identifier,)).fetchone()
            return dict(row) if row else None
        finally:
            connection.close()

    def list(self, camera=None, status=None, limit=100, offset=0):
        connection = self.connect()
        clauses, params = [], []
        for column, value in (("camera", camera), ("status", status)):
            if value is not None:
                clauses.append(f"{column}=?")
                params.append(value)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        try:
            with connection:
                connection.execute("BEGIN")
                total = connection.execute("SELECT COUNT(*) FROM alerts" + where, params).fetchone()[0]
                rows = connection.execute("SELECT * FROM alerts" + where + " ORDER BY fecha_hora DESC, id DESC LIMIT ? OFFSET ?",
                                          (*params, limit, offset)).fetchall()
            return dict(items=[dict(row) for row in rows], total=total, limit=limit, offset=offset)
        finally:
            connection.close()
