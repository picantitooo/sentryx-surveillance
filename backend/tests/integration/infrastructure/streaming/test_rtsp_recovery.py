"""Regressions for schema locks and RTSP recovery; no camera connection."""
import asyncio
from concurrent.futures import ThreadPoolExecutor
from types import SimpleNamespace

import pytest

from app.infrastructure.persistence.alerts import AlertStore
from app.domain.alerts import EventPolicy
from app.infrastructure.persistence.detections import DetectionStore


def test_rtsp_reconnects_when_alerts_logs_and_close_fail(configured, monkeypatch):
    import app.infrastructure.streaming.rtsp as module
    from app.domain.pipeline import PipelineConfig, WindowBuffer
    from app.infrastructure.streaming.webrtc import Session

    class BrokenStore:
        def interrupt(self, *args):
            raise RuntimeError("storage unavailable")

        def emit(self, *args, **kwargs):
            raise RuntimeError("logs unavailable")

    async def exercise():
        receiver = module.RTSPReceiver(lambda *args: {}, detection_store=configured, alert_store=BrokenStore(),
                                       log_store=BrokenStore())
        session = Session(pc=module._RTSPPeer(), source_id="cam",
                          buffer=WindowBuffer(PipelineConfig()), alert_policy=EventPolicy())
        session.camera_config = receiver.default_camera
        receiver.sessions[session.id] = session
        opened = []

        class Container:
            def decode(self, **kwargs):
                return iter(())

            def close(self):
                raise RuntimeError("close failed")

        def open_stream(*args, **kwargs):
            opened.append(1)
            return Container()

        async def retry_sleep(delay):
            assert delay == 3
            if len(opened) == 2:
                receiver.sessions.pop(session.id)

        monkeypatch.setattr(module.av, "open", open_stream)
        monkeypatch.setattr(module.asyncio, "sleep", retry_sleep)
        await asyncio.wait_for(receiver._read_loop(session), 5)
        assert len(opened) == 2
        assert session.pending_alert_interruption
        assert session.rtsp_status == "reconnecting"

    asyncio.run(exercise())
