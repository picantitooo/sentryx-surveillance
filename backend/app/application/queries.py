"""Read use cases shared by detection, alert and operational log repositories."""
import unicodedata
from datetime import datetime, time, timedelta, timezone
from typing import get_args

from app.application.errors import InvalidInput, NotFound, Unavailable
from app.application.ports import AlertRepository, DetectionRepository, LogRepository
from app.domain.inference import Classes

# Lima no tiene horario de verano: un desfase fijo evita depender de tzdata en Windows.
LIMA_OFFSET = -5
LIMA = timezone(timedelta(hours=LIMA_OFFSET))
ISO = "%Y-%m-%dT%H:%M:%S"
CLASS_NAMES = get_args(Classes)


def _fold(text):
    """Sin tildes, en minúsculas y con espacios en lugar de _ o -: 'agresion_fisica' == 'Agresión física'."""
    text = "".join(ch for ch in unicodedata.normalize("NFKD", text) if not unicodedata.combining(ch))
    return " ".join(text.lower().replace("_", " ").replace("-", " ").split())


def matching_classes(*texts):
    """Clases cuyo nombre contiene todos los textos dados; None si no hay texto (sin filtro), () si ninguna coincide."""
    wanted = [_fold(text) for text in texts if text and text.strip()]
    if not wanted:
        return None
    return tuple(name for name in CLASS_NAMES if all(part in _fold(name) for part in wanted))


def record_filters(*class_texts, since=None, until=None):
    """Filtros de repositorio: clases exactas y [inicio de `since`, fin de `until`) en días de Lima, como texto ISO UTC."""
    if since is not None and until is not None and since > until:
        raise InvalidInput("since debe ser menor o igual a until")
    filters = {}
    classes = matching_classes(*class_texts)
    if classes is not None:
        filters["classes"] = classes
    if since is not None:
        filters["date_from"] = datetime.combine(since, time(), LIMA).astimezone(timezone.utc).strftime(ISO)
    if until is not None:
        end = datetime.combine(until, time(), LIMA) + timedelta(days=1)
        filters["date_to"] = end.astimezone(timezone.utc).strftime(ISO)
    return filters


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

    def count(self, *args, **filters):
        try:
            return self.repository.count(*args, **filters)
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
