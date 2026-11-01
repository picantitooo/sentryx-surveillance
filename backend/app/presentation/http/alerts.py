"""Alert HTTP adapter."""
from fastapi import APIRouter, Query
from typing import Literal


def alerts_router(service):
    router = APIRouter(prefix='/alerts', tags=['Alertas EN-4'])

    @router.get('')
    def list_alerts(camera: str | None = None, status: Literal['active', 'closed', 'interrupted'] | None = None,
                    limit: int = Query(100, ge=1, le=500), offset: int = Query(0, ge=0)):
        return service.list(camera, status, limit, offset)

    @router.get('/{alert_id}')
    def get_alert(alert_id: str):
        return service.get(alert_id)

    return router
