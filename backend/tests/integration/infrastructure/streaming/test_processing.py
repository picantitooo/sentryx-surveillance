"""The shared processing use case preserves temporal alert semantics."""
import asyncio

import pytest


@pytest.mark.parametrize("numbers,active", [([1, 2], True), ([1, 3], False)])
def test_window_processor_persists_detections_and_resets_on_gaps(configured, tmp_path, numbers, active):
    from app.domain.alerts import EventPolicy
    from app.domain.pipeline import PipelineConfig, WindowBuffer
    from app.infrastructure.persistence.alerts import AlertStore
    from app.infrastructure.persistence.inference_logs import InferenceLogStore
    from app.infrastructure.streaming.rtsp import RTSPReceiver, _RTSPPeer
    from app.infrastructure.streaming.webrtc import Session

    async def exercise():
        alerts = AlertStore(configured.path)
        logs = InferenceLogStore(tmp_path / "processing-logs.db")
        receiver = RTSPReceiver(lambda *args: None, detection_store=configured, alert_store=alerts,
                                log_store=logs, predict_frames=lambda frames, timestamp: {
                                    "clase": "Hurto", "confianza": .95,
                                    "timestamp": timestamp, "simulated": True})
        session = Session(pc=_RTSPPeer(), source_id="test",
                          buffer=WindowBuffer(PipelineConfig()), alert_policy=EventPolicy())
        receiver.sessions[session.id] = session
        for number in numbers:
            session.buffer.queue.put_nowait((number, [(object(), float(number))]))
        task = asyncio.create_task(receiver.process_windows(session))
        try:
            await asyncio.wait_for(session.buffer.queue.join(), timeout=5)
            assert session.windows_processed == 2
            assert session.processing_errors == 0
            assert len(configured.list()) == 2
            assert session.latest_result["alert"]["active"] is active
            assert alerts.list(status="active")["total"] == int(active)
            assert logs.list(event_type="inference_completed")["total"] == 2
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
            await receiver.close(session.id)

    asyncio.run(exercise())
