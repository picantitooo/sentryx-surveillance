"""Clave compartida para las rutas de datos, privadas incluso al usar Funnel."""
import os
import secrets

from fastapi.openapi.utils import get_openapi
from starlette.responses import JSONResponse


class ApiKeyGuard:
    PUBLIC_PATHS = {"/health", "/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc"}

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["method"] == "OPTIONS" or scope["path"] in self.PUBLIC_PATHS:
            return await self.app(scope, receive, send)
        expected = os.getenv("SENTRIX_CONTROL_API_KEY", "")
        provided = next((value for name, value in scope["headers"] if name.lower() == b"x-api-key"), b"")
        if not expected or not provided or not secrets.compare_digest(provided, expected.encode("utf-8")):
            return await JSONResponse({"detail": "API key invalida"}, status_code=401)(scope, receive, send)
        await self.app(scope, receive, send)


def document_api_key(app):
    """Permitir usar Authorize en Swagger para las rutas protegidas."""
    def openapi():
        if app.openapi_schema is not None:
            return app.openapi_schema
        schema = get_openapi(title=app.title, version=app.version, description=app.description, routes=app.routes)
        schema.setdefault("components", {}).setdefault("securitySchemes", {})["ControlApiKey"] = {"type": "apiKey", "in": "header", "name": "X-API-Key"}
        for path, operations in schema["paths"].items():
            if path in ApiKeyGuard.PUBLIC_PATHS:
                continue
            for operation in operations.values():
                if isinstance(operation, dict) and "responses" in operation:
                    operation["security"] = [{"ControlApiKey": []}]
        app.openapi_schema = schema
        return schema
    app.openapi = openapi
