from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded

from app.config import settings


def _client_ip(request: Request) -> str:
    if settings.TRUST_PROXY:
        forwarded = request.headers.get("X-Forwarded-For", "")
        if forwarded:
            return forwarded.split(",")[0].strip()

    return request.client.host if request.client else "unknown"


limiter = Limiter(key_func=_client_ip)


def rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    headers = dict(getattr(exc, "headers", {}) or {})
    headers.setdefault("Retry-After", "60")

    return JSONResponse(
        status_code=429,
        content={
            "error": {
                "code": "TOO_MANY_REQUESTS",
                "message": "Rate limit excedido",
            }
        },
        headers=headers,
    )
