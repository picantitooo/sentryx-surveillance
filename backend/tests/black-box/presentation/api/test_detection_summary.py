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


def test_detection_filters_by_class_text_and_lima_days(api_client):
    store = api_client.app.state.detection_store
    seed(store, [
        ("camara1", "2026-11-10T05:00:00+00:00", "Agresión física"),   # 10-11 00:00 en Lima
        ("camara1", "2026-11-10T15:00:00+00:00", "Robo"),
        ("camara2", "2026-11-11T04:59:59Z", "Robo"),                    # 10-11 23:59 en Lima, formato con Z
        ("camara1", "2026-11-11T05:00:00+00:00", "Normal"),            # 11-11 en Lima
        ("camara2", "2026-11-12T16:00:00+00:00", "Vandalismo"),
    ])

    def total(**params):
        response = api_client.get("/detections", params=params)
        assert response.status_code == 200, response.text
        return int(response.headers["X-Total-Count"]), [item["clase"] for item in response.json()]

    assert total(clase="robo") == (2, ["Robo", "Robo"])
    assert total(clase="agresion_fisica") == (1, ["Agresión física"])  # el valor que envía el panel
    assert total(q="AGRES")[0] == 1                                    # sin importar tildes ni mayúsculas
    assert total(q="xyz") == (0, [])                                  # sin coincidencias: vacío, no la lista completa
    assert total(since="2026-11-10", until="2026-11-10")[0] == 3       # el día completo de Lima
    assert total(since="2026-11-11")[0] == 2
    assert total(until="2026-11-10")[0] == 3
    assert total(clase="robo", camera="camara2", since="2026-11-10", until="2026-11-10") == (1, ["Robo"])
    assert api_client.get("/detections", params={"since": "2026-11-12", "until": "2026-11-10"}).status_code == 422
    assert api_client.get("/detections", params={"since": "ayer"}).status_code == 422


def test_alert_list_filters_by_class(api_client):
    store = api_client.app.state.alert_store
    connection = store.connect()
    try:
        with connection:
            for index, (camera, clase, status) in enumerate([("camara1", "Robo", "closed"),
                                                             ("camara1", "Agresión física", "closed"),
                                                             ("camara2", "Robo", "active")]):
                detection = f"d{index}"
                connection.execute("INSERT INTO detections VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                                   (detection, camera, f"2026-11-10T15:00:0{index}+00:00", clase, 0.9, float(index),
                                    0, None, None, None))
                connection.execute(
                    "INSERT INTO alerts (id, detection_id, camera, session_id, clase, confianza, threshold, timestamp, "
                    "fecha_hora, timestamp_inicio, status) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (f"a{index}", detection, camera, f"s{index}", clase, 0.9, 0.6, float(index),
                     f"2026-11-10T15:00:0{index}+00:00", float(index), status))
    finally:
        connection.close()

    def classes(**params):
        response = api_client.get("/alerts", params=params)
        assert response.status_code == 200, response.text
        body = response.json()
        return body["total"], sorted(item["clase"] for item in body["items"])

    assert classes() == (3, ["Agresión física", "Robo", "Robo"])
    assert classes(clase="robo") == (2, ["Robo", "Robo"])
    assert classes(clase="Agresion") == (1, ["Agresión física"])
    assert classes(clase="robo", status="active") == (1, ["Robo"])
    assert classes(clase="nada") == (0, [])
