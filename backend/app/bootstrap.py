"""API SentriX: VideoMAE CUDA por defecto y simulador explícito para pruebas."""
import logging
import asyncio
import os
import time
from contextlib import asynccontextmanager
from fastapi.middleware.cors import CORSMiddleware
from app.infrastructure.streaming.webrtc import WebRTCReceiver
from fastapi import FastAPI
from app.infrastructure.persistence.detections import DetectionStore
from app.infrastructure.persistence.inference_logs import InferenceLogStore
from app.presentation.http.logs import logs_router
from app.infrastructure.persistence.alerts import AlertStore
from app.domain.alerts import EventPolicy
from app.presentation.http.alerts import alerts_router
from app.presentation.http.security import ApiKeyGuard, document_api_key

from app.domain.inference import Window, Prediction
from app.application.ports import Predictor
from app.application.inference import InferenceService
from app.application.queries import RecordQueries
from app.application.cameras import CameraService
from app.application.errors import ApplicationError, InvalidInput, InvalidOffer, NotFound, Conflict, Unavailable
from app.infrastructure.inference.mock import MockPredictor
from app.infrastructure.persistence.cameras import CameraStore
from app.infrastructure.settings import event_policy as configured_event_policy
from app.presentation.http.inference import inference_router
from app.presentation.http.body_limit import BodyLimit
from app.presentation.http.streaming import rtsp_routers, webrtc_router
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)

def create_app(predictor: Predictor | None = None, *, mode: str | None = None,
               transport: str | None = None, detection_db=None, log_db=None):
    database_url = os.getenv("SENTRIX_DATABASE_URL")
    if not database_url and not (detection_db or os.getenv("SENTRIX_DETECTION_DB")):
        raise ValueError("Configurar SENTRIX_DATABASE_URL con una conexión PostgreSQL")
    store = DetectionStore(detection_db or database_url or os.getenv("SENTRIX_DETECTION_DB"))
    log_store = InferenceLogStore(log_db or database_url or os.getenv("SENTRIX_LOG_DB") or store.path)
    alert_store = AlertStore(store.path)
    event_policy = configured_event_policy()
    selected_mode = mode or os.getenv("SENTRIX_PREDICTOR", "videomae")
    real_mode = predictor is None and selected_mode == "videomae"
    if predictor is None and selected_mode not in ("videomae", "mock"):
        raise ValueError("SENTRIX_PREDICTOR debe ser videomae o mock")
    selected_transport = transport or os.getenv("SENTRIX_VIDEO_TRANSPORT", "rtsp")
    if selected_transport not in ("webrtc", "rtsp"):
        raise ValueError("SENTRIX_VIDEO_TRANSPORT debe ser webrtc o rtsp")
    receiver_type = WebRTCReceiver
    receiver_options = {"detection_store": store, "log_store": log_store, "alert_store": alert_store}
    policy_factory = lambda: EventPolicy(event_policy.thresholds)
    if selected_transport == "rtsp":
        from app.infrastructure.streaming.rtsp import RTSPReceiver
        receiver_type = RTSPReceiver
    def predict_window(frames, timestamp):
        window = Window(frames=frames, timestamp=timestamp)
        return Prediction.model_validate(app.state.predictor.predict(window)).model_dump(exclude_none=True)
    if real_mode:
        from app.infrastructure.inference.videomae import VideoMAEPredictor, load_metadata, config_from_metadata
        from app.domain.pipeline import VideoMAEBuffer
        receiver = receiver_type(
            predict_window, config_from_metadata(load_metadata()), buffer_factory=VideoMAEBuffer,
            predict_frames=lambda frames, timestamp: Prediction.model_validate(
                app.state.predictor.predict_frames(frames, timestamp)).model_dump(exclude_none=True),
            policy_factory=policy_factory, **receiver_options)
    else:
        receiver = receiver_type(predict_window, policy_factory=policy_factory, **receiver_options)
    camera_service = (CameraService(CameraStore(store.path), receiver, receiver.default_camera, receiver.lock)
                      if selected_transport == "rtsp" else None)
    @asynccontextmanager
    async def lifespan(app):
        if database_url:
            # Fallar al iniciar si la conexión principal no está disponible.
            def initialize_storage():
                for persistent_store in (store, alert_store, log_store):
                    connection = persistent_store.connect()
                    try:
                        with connection:
                            connection.execute("SELECT 1")
                    finally:
                        connection.close()
            await asyncio.to_thread(initialize_storage)
        if selected_transport == "rtsp":
            await camera_service.initialize_cameras()
        try:
            try:
                await asyncio.to_thread(alert_store.interrupt, reason="service_restarted")
            except Exception:
                logger.exception("No se pudieron recuperar las alertas pendientes")
            if real_mode:
                started = time.perf_counter()
                await asyncio.to_thread(log_store.emit, "model_loading", "Iniciando carga de VideoMAE")
                try:
                    provider = os.getenv("SENTRIX_PROVIDER", "cuda")
                    if provider not in ("cuda", "cpu"):
                        raise ValueError("SENTRIX_PROVIDER debe ser cuda o cpu; no hay fallback automático")
                    logger.info("Cargando VideoMAE (%s); esperar antes de conectar la fuente", provider)
                    app.state.predictor = await asyncio.to_thread(VideoMAEPredictor, provider=provider)
                except Exception:
                    await asyncio.to_thread(log_store.emit, "model_error", "No se pudo cargar el modelo",
                                            level="ERROR", processing_ms=round((time.perf_counter()-started)*1000, 3))
                    raise
                logger.info("Modelo listo: %s", app.state.predictor.health())
                await asyncio.to_thread(log_store.emit, "model_ready", "Modelo cargado y calentamiento completado",
                                        processing_ms=round((time.perf_counter()-started)*1000, 3))
            await asyncio.to_thread(log_store.emit, "service_started", "Servicio de inferencia iniciado")
            yield
        finally:
            await receiver.shutdown()
            await asyncio.to_thread(log_store.emit, "service_stopped", "Servicio de inferencia detenido")
            if real_mode:
                app.state.predictor = None
    app = FastAPI(title="SentriX · Servicio de inferencia", version="0.6.0", lifespan=lifespan,
                  description="VideoMAE CUDA; recepción RTSP/RTSPS o WebRTC y consulta de resultados HTTP.")
    app.add_middleware(BodyLimit)
    app.add_middleware(ApiKeyGuard)
    origins = [value.strip() for value in os.getenv("FRONTEND_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173,https://sentrix-vercel-upload.vercel.app").split(",") if value.strip()]
    app.add_middleware(CORSMiddleware, allow_origins=origins,
                       allow_credentials=True, allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
                       allow_headers=["Content-Type", "Authorization", "X-API-Key"],
                       expose_headers=["X-Detection-ID"])
    @app.exception_handler(ApplicationError)
    async def application_error(request, error):
        status = {InvalidInput: 422, InvalidOffer: 400, NotFound: 404, Conflict: 409, Unavailable: 503}.get(type(error), 500)
        return JSONResponse(status_code=status, content={"detail": str(error)})

    if selected_transport == "rtsp":
        for router in rtsp_routers(camera_service):
            app.include_router(router)
    else:
        app.include_router(webrtc_router(receiver))
    app.include_router(logs_router(RecordQueries(log_store,
        unavailable="Almacenamiento de logs no disponible", missing="Log no encontrado")))
    app.include_router(alerts_router(RecordQueries(alert_store,
        unavailable="Almacenamiento de alertas no disponible", missing="Alerta no encontrada")))
    app.state.video_receiver = receiver
    app.state.detection_store = store
    app.state.log_store = log_store
    app.state.alert_store = alert_store
    app.state.predictor = predictor if predictor is not None else (None if real_mode else MockPredictor())

    inference_service = InferenceService(lambda: app.state.predictor, store, log_store, real_mode=real_mode)
    detection_queries = RecordQueries(store, unavailable="Almacenamiento de detecciones no disponible",
                                      missing="Detección no encontrada")
    app.include_router(inference_router(app, detection_queries, receiver, inference_service,
                       real_mode=real_mode, selected_transport=selected_transport, mock_type=MockPredictor))
    document_api_key(app)
    return app
