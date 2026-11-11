"""Read use cases shared by detection, alert and operational log repositories."""
from datetime import datetime, time, timedelta, timezone

from app.application.errors import InvalidInput, NotFound, Unavailable
from app.application.ports import AlertRepository, DetectionRepository, LogRepository

# Lima no tiene horario de verano: un desfase fijo evita depender de tzdata en Windows.
LIMA_OFFSET = -5
LIMA = timezone(timedelta(hours=LIMA_OFFSET))
ISO = "%Y-%m-%dT%H:%M:%S"


class RecordQueries:
    def __init__(self, repository: AlertRepository | DetectionRepository | LogRepository,
                 *, unavailable: str, missing: str):
        self.repository = repository
        self.unavailable = unavailable
        self.missing = missing

    def list(self, *args, **filters):
        date_from, date_to = filters.get("date_from"), filters.get("date_to")
        if date_from is not None and date_to is not None and date_from > date_to:
            raise InvalidInput("date_from debe ser menor o igual a date_to")
        try:
            return self.repository.list(*args, **filters)
        except Exception:
            raise Unavailable(self.unavailable) from None

    def get(self, identifier):
        try:
            record = self.repository.get(identifier)
        except Exception:
            raise Unavailable(self.unavailable) from None
        if record is None:
            raise NotFound(self.missing)
        return record

    def count(self, *args):
        try:
            return self.repository.count(*args)
        except Exception:
            raise Unavailable(self.unavailable) from None

    def daily_summary(self, day=None):
        """Detecciones de un día de Lima: total, por clase, por cámara y por hora local."""
        day = day or datetime.now(LIMA).date()
        start = datetime.combine(day, time(), LIMA).astimezone(timezone.utc)
        try:
            rows = self.repository.summary(start.strftime(ISO), (start + timedelta(days=1)).strftime(ISO))
        except Exception:
            raise Unavailable(self.unavailable) from None
        by_class, by_camera = {}, {}
        hours = [{"hour": hour, "total": 0, "anomalies": 0} for hour in range(24)]
        for clase, camera, utc_hour, total in rows:
            by_class[clase] = by_class.get(clase, 0) + total
            by_camera[camera] = by_camera.get(camera, 0) + total
            slot = hours[(utc_hour + LIMA_OFFSET) % 24]
            slot["total"] += total
            if clase != "Normal":
                slot["anomalies"] += total
        total = sum(by_class.values())
        return {"date": day.isoformat(), "timezone": "America/Lima", "total": total,
                "anomalies": total - by_class.get("Normal", 0), "by_class": by_class, "by_camera": by_camera,
                "by_hour": hours}
