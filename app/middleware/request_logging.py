from __future__ import annotations

import time

from app.core.logging import get_logger
from app.core.metrics import increment_requests_total
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = get_logger(__name__)


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        start_time = time.perf_counter()
        response: Response | None = None

        try:
            response = await call_next(request)
            return response
        finally:
            increment_requests_total()
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            request_id = getattr(request.state, "request_id", None)
            if request_id is None and response is not None:
                request_id = response.headers.get("X-Request-ID")

            logger.info(
                "http.request",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code if response is not None else 500,
                duration_ms=duration_ms,
                request_id=request_id,
            )
