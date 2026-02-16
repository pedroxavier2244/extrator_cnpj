from __future__ import annotations

import time
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.openapi.models import APIKey, APIKeyIn
from fastapi.security import APIKeyHeader
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.v1.cnpj import router as cnpj_router
from app.api.v1.empresas import router as empresas_router
from app.api.v1.metrics import router as metrics_router
from app.config import settings
from app.core.cache import get_cache
from app.core.exceptions import AppError
from app.core.logging import get_logger, setup_logging
from app.core.metrics import get_uptime_seconds, increment_db_errors_total, set_startup_time
from app.database import SessionLocal
from app.middleware.api_key import APIKeyMiddleware
from app.middleware.rate_limit import limiter, rate_limit_exceeded_handler
from app.middleware.request_id import RequestIDMiddleware
from app.middleware.request_logging import RequestLoggingMiddleware
from app.middleware.security_headers import SecurityHeadersMiddleware
from app.schemas.api_responses import ErrorResponse, HealthResponse

APP_VERSION = "1.0.0"
logger = get_logger(__name__)


def _get_request_id(request: Request) -> str | None:
    request_id = getattr(request.state, "request_id", None)
    if request_id:
        return request_id
    return request.headers.get("X-Request-ID")


@asynccontextmanager
async def lifespan(_: FastAPI):
    setup_logging()
    set_startup_time()
    get_cache()
    logger.info("api.startup", version=APP_VERSION)
    yield
    logger.info("api.shutdown")


api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)

app = FastAPI(
    title=settings.APP_NAME,
    description="API de consulta de dados publicos de CNPJ da Receita Federal",
    version=APP_VERSION,
    docs_url="/docs" if settings.ENVIRONMENT != "production" else None,
    redoc_url="/redoc" if settings.ENVIRONMENT != "production" else None,
    openapi_tags=[
        {"name": "cnpj", "description": "Consulta de CNPJ individual e em lote"},
        {"name": "empresas", "description": "Busca de empresas por razao social"},
    ],
    lifespan=lifespan,
    swagger_ui_init_oauth={},
)

def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    from fastapi.openapi.utils import get_openapi
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
        tags=app.openapi_tags,
    )
    schema["components"]["securitySchemes"] = {
        "APIKeyHeader": {
            "type": "apiKey",
            "in": "header",
            "name": "X-API-Key",
        }
    }
    schema["security"] = [{"APIKeyHeader": []}]
    app.openapi_schema = schema
    return schema

app.openapi = custom_openapi

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_exceeded_handler)

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(RequestIDMiddleware)
app.add_middleware(
    APIKeyMiddleware,
    api_keys=settings.API_KEYS,
    public_paths={
        f"{settings.API_V1_PREFIX}/health",
        "/docs",
        "/redoc",
        "/openapi.json",
    },
)

app.include_router(cnpj_router, prefix=settings.API_V1_PREFIX)
app.include_router(empresas_router, prefix=settings.API_V1_PREFIX)
app.include_router(metrics_router, prefix=settings.API_V1_PREFIX)


@app.exception_handler(AppError)
def handle_app_error(request: Request, exc: AppError) -> JSONResponse:
    if exc.status_code >= 500:
        increment_db_errors_total()

    payload = ErrorResponse(
        error={
            "code": exc.code,
            "message": exc.message,
            "request_id": _get_request_id(request),
        }
    )
    return JSONResponse(status_code=exc.status_code, content=payload.model_dump())


@app.exception_handler(RequestValidationError)
def handle_request_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = exc.errors()
    message = errors[0].get("msg", "Dados de requisicao invalidos") if errors else "Dados de requisicao invalidos"

    payload = ErrorResponse(
        error={
            "code": "VALIDATION_ERROR",
            "message": message,
            "request_id": _get_request_id(request),
        }
    )
    return JSONResponse(status_code=422, content=payload.model_dump())


@app.exception_handler(Exception)
def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    if isinstance(exc, SQLAlchemyError):
        increment_db_errors_total()

    logger.exception("api.unhandled_exception", path=request.url.path)

    payload = ErrorResponse(
        error={
            "code": "INTERNAL_ERROR",
            "message": "Erro interno",
            "request_id": _get_request_id(request),
        }
    )
    return JSONResponse(status_code=500, content=payload.model_dump())


@app.get(
    f"{settings.API_V1_PREFIX}/health",
    response_model=HealthResponse,
    summary="Health check",
    description="Verifica disponibilidade de banco, cache e estado geral da API.",
)
@limiter.limit("120/minute")
def health(request: Request, response: Response) -> HealthResponse:
    cache_backend = get_cache()

    if not (cache_backend.redis_url or "").strip():
        cache_status = "disabled"
    elif cache_backend.enabled:
        cache_status = "ok"
    else:
        cache_status = "unavailable"

    db_started = time.perf_counter()
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
    except Exception:
        increment_db_errors_total()
        response.status_code = 503
        return HealthResponse(
            status="unhealthy",
            database="unavailable",
            cache=cache_status,
            version=APP_VERSION,
            uptime_seconds=get_uptime_seconds(),
        )

    db_duration = time.perf_counter() - db_started
    overall_status = "degraded" if db_duration > 0.2 else "ok"

    return HealthResponse(
        status=overall_status,
        database="ok",
        cache=cache_status,
        version=APP_VERSION,
        uptime_seconds=get_uptime_seconds(),
    )
