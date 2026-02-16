from __future__ import annotations

from collections.abc import Iterable

from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class APIKeyMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, api_keys: Iterable[str], public_paths: Iterable[str]):
        super().__init__(app)
        self.api_keys = {key.strip() for key in api_keys if key and key.strip()}
        self.public_paths = {path.strip() for path in public_paths if path and path.strip()}

    def _is_public_path(self, path: str) -> bool:
        if path in self.public_paths:
            return True

        if path == "/docs" or path.startswith("/docs/"):
            return True
        if path == "/redoc" or path.startswith("/redoc/"):
            return True
        if path == "/openapi.json":
            return True

        return False

    async def dispatch(self, request: Request, call_next) -> Response:
        if not self.api_keys:
            return await call_next(request)

        if request.method.upper() == "OPTIONS":
            return await call_next(request)

        if self._is_public_path(request.url.path):
            return await call_next(request)

        api_key = request.headers.get("X-API-Key", "").strip()
        if api_key not in self.api_keys:
            return JSONResponse(
                status_code=401,
                content={
                    "error": {
                        "code": "UNAUTHORIZED",
                        "message": "API Key invalida ou ausente",
                    }
                },
            )

        return await call_next(request)
