from __future__ import annotations

from fastapi import FastAPI
from sqlalchemy import text

from app.api.v1.cnpj import router as cnpj_router
from app.api.v1.empresas import router as empresas_router
from app.config import settings
from app.core.logging import setup_logging
from app.database import SessionLocal
from app.schemas.api_responses import HealthResponse

setup_logging()

app = FastAPI(title=settings.APP_NAME)
app.include_router(cnpj_router, prefix=settings.API_V1_PREFIX)
app.include_router(empresas_router, prefix=settings.API_V1_PREFIX)


@app.get(f"{settings.API_V1_PREFIX}/health", response_model=HealthResponse)
def health() -> HealthResponse:
    with SessionLocal() as db:
        db.execute(text("SELECT 1"))
    return HealthResponse(status="ok")
