from app.domain.camera import CameraRegistration
from app.infrastructure.persistence.cameras import CameraStore


def test_camera_sql_roundtrip_and_update(tmp_path):
    path = tmp_path / "cameras.db"
    store = CameraStore(path)
    camera = CameraRegistration(source_id="cam", password="integration-only")
    assert store.save(camera) is True
    assert store.save(camera) is False
    restored = CameraStore(path).get("cam")
    assert restored.private_config() == camera.private_config()
    restored.enabled = False
    assert store.save(restored, update=True) is True
    assert store.list()[0].enabled is False
    assert store.delete("cam") is True
    assert store.get("cam") is None
