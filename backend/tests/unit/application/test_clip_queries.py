"""El panel recibe estado y URL temporal del clip según el contrato recording/ready/partial/missing."""
import pytest

from app.application.clips import ClipQueries
from app.application.errors import NotFound, Unavailable


class Rows:
    def __init__(self, rows):
        self.rows = rows

    def get(self, identifier):
        return self.rows.get(identifier)


class Storage:
    def url(self, key, expires):
        return f"https://bucket.example/{key}?expira={expires}"


ALERTS = Rows({"activa": {"status": "active"}, "cerrada": {"status": "closed"}, "subida": {"status": "closed"},
               "local": {"status": "interrupted"}, "subiendo": {"status": "closed"}})
CLIPS = Rows({
    "subida": {"status": "ready", "object_key": "camara1/subida.mp4", "duration_seconds": 12.5, "size_bytes": 900},
    "local": {"status": "partial", "object_key": None, "local_path": "C:/clips/local.mp4", "reason": "window_gap"},
    "subiendo": {"status": "uploading", "object_key": None}})


@pytest.mark.parametrize("alert,status,url,storage", [
    ("activa", "recording", None, None),
    ("cerrada", "missing", None, None),
    ("subida", "ready", "https://bucket.example/camara1/subida.mp4?expira=300", "remote"),
    ("local", "partial", None, "local"),
    ("subiendo", "recording", None, None),
])
def test_clip_status_for_the_panel(alert, status, url, storage):
    clip = ClipQueries(ALERTS, CLIPS, Storage(), url_seconds=300).get(alert)
    assert (clip["status"], clip["url"], clip["storage"]) == (status, url, storage)


def test_unknown_alert_and_broken_storage():
    with pytest.raises(NotFound):
        ClipQueries(ALERTS, CLIPS).get("no-existe")

    class Broken:
        def get(self, identifier):
            raise RuntimeError("Neon caído")

    with pytest.raises(Unavailable):
        ClipQueries(Broken(), CLIPS).get("activa")


def test_clip_left_open_by_a_dead_worker_is_reported_missing():
    from datetime import datetime, timedelta, timezone
    old = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    recent = datetime.now(timezone.utc).isoformat()
    alerts = Rows({"huerfana": {"status": "interrupted"}, "subiendo": {"status": "closed"},
                   "activa": {"status": "active"}})
    clips = Rows({"huerfana": {"status": "recording", "updated_at": old},
                  "subiendo": {"status": "uploading", "updated_at": recent},
                  "activa": {"status": "recording", "updated_at": old}})
    queries = ClipQueries(alerts, clips, Storage())
    lost = queries.get("huerfana")
    assert (lost["status"], lost["reason"], lost["url"]) == ("missing", "clip_abandoned", None)
    assert queries.get("subiendo")["status"] == "recording"   # acaba de cerrar: sigue subiendo
    assert queries.get("activa")["status"] == "recording"     # evento largo aún abierto
