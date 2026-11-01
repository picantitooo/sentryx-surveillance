import pytest


@pytest.mark.parametrize("backend_server", ["open"], indirect=True)
def test_restart_recovers_open_alert_and_preserves_history(backend_server):
    identifier = "e2e_recovery"
    client = backend_server.client
    assert client.post("/cameras", json={"source_id": identifier}).status_code == 201
    assert client.post("/sources/start", json={"source_id": identifier}).status_code == 200
    backend_server.wait_for(f"/sources/{identifier}/status", lambda row: row["windows_processed"] == 2)
    before = client.get("/alerts", params={"camera": identifier}).json()["items"][0]
    assert before["status"] == "active"
    detection_ids = {row["id"] for row in client.get("/detections", params={"camera": identifier}).json()}

    # Abruptly stop only our test child, leaving the active event for startup recovery.
    backend_server.restart(graceful=False)
    client = backend_server.client
    recovered = client.get(f"/alerts/{before['id']}").json()
    assert recovered["status"] == "interrupted"
    assert recovered["interruption_reason"] == "service_restarted"
    assert recovered["timestamp_fin"] is None
    assert {row["id"] for row in client.get("/detections", params={"camera": identifier}).json()} == detection_ids
    assert client.get(f"/sources/{identifier}/status").json()["active"] is False
    assert client.get("/alerts", params={"camera": identifier, "status": "active"}).json()["total"] == 0
