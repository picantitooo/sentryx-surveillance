"""Resumen diario y total de detecciones para el tablero del panel."""
from datetime import datetime, timedelta, timezone

from app.application.queries import LIMA


def seed(store, rows):
    connection = store.connect()
    try:
        with connection:
            for index, (camera, moment, clase) in enumerate(rows):
                connection.execute("INSERT INTO detections VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                   (f"d{index}", camera, moment, clase, 0.9, float(index), 0, None, None, None))
    finally:
        connection.close()


def test_summary_counts_one_lima_day_by_class_camera_and_hour(api_client):
    store = api_client.app.state.detection_store
    seed(store, [
        ("camara1", "2026-11-10T05:00:00+00:00", "Normal"),          # 00:00 en Lima: primer instante del día
        ("camara1", "2026-11-10T15:30:00.123456+00:00", "Robo"),      # 10:30 en Lima
        ("camara2", "2026-11-10T15:45:00Z", "Normal"),                # formato con Z
        ("camara2", "2026-11-11T04:59:59+00:00", "Hurto"),            # 23:59 en Lima: último instante
        ("camara1", "2026-11-10T04:59:59+00:00", "Robo"),             # día anterior en Lima
        ("camara1", "2026-11-11T05:00:00+00:00", "Robo"),             # día siguiente en Lima
    ])
    response = api_client.get("/detections/summary", params={"date": "2026-11-10"})
    assert response.status_code == 200
    body = response.json()
    assert (body["date"], body["timezone"], body["total"], body["anomalies"]) == ("2026-11-10", "America/Lima", 4, 2)
    assert body["by_class"] == {"Normal": 2, "Robo": 1, "Hurto": 1}
    assert body["by_camera"] == {"camara1": 2, "camara2": 2}
    hours = {item["hour"]: (item["total"], item["anomalies"]) for item in body["by_hour"]}
    assert len(body["by_hour"]) == 24 and sum(total for total, _ in hours.values()) == 4
    assert (hours[0], hours[10], hours[23]) == ((1, 0), (2, 1), (1, 1))


def test_summary_defaults_to_today_and_rejects_bad_input(api_client):
    store = api_client.app.state.detection_store
    seed(store, [("camara1", datetime.now(timezone.utc).isoformat(), "Normal"),
                 ("camara1", (datetime.now(timezone.utc) - timedelta(days=3)).isoformat(), "Normal")])
    body = api_client.get("/detections/summary").json()
    assert body["date"] == datetime.now(LIMA).date().isoformat() and body["total"] == 1
    assert api_client.get("/detections/summary", params={"date": "ayer"}).status_code == 422
    assert api_client.get("/detections/summary", headers={"X-API-Key": "otra"}).status_code == 401


def test_detection_list_keeps_its_shape_and_reports_the_total(api_client):
    store = api_client.app.state.detection_store
    seed(store, [("camara1", f"2026-11-10T15:00:0{i}+00:00", "Normal") for i in range(5)]
               + [("camara2", "2026-11-10T16:00:00+00:00", "Robo")])
    page = api_client.get("/detections", params={"limit": 2})
    assert isinstance(page.json(), list) and len(page.json()) == 2
    assert page.headers["X-Total-Count"] == "6"
    assert api_client.get("/detections", params={"camera": "camara2"}).headers["X-Total-Count"] == "1"
