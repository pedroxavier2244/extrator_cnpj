from __future__ import annotations

from fastapi import FastAPI, HTTPException
from sqlalchemy import text

from app.api.v1.cnpj import router as cnpj_router
from app.api.v1.empresas import router as empresas_router
from app.config import settings
from app.core.cache import get_cache
from app.core.logging import setup_logging
from app.database import SessionLocal
from app.schemas.api_responses import HealthResponse

setup_logging()
get_cache()

app = FastAPI(title=settings.APP_NAME)
app.include_router(cnpj_router, prefix=settings.API_V1_PREFIX)
app.include_router(empresas_router, prefix=settings.API_V1_PREFIX)


@app.get(f"{settings.API_V1_PREFIX}/health", response_model=HealthResponse)
def health() -> HealthResponse:
    try:
        with SessionLocal() as db:
            db.execute(text("SELECT 1"))
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Database unavailable") from exc
    return HealthResponse(status="ok")
