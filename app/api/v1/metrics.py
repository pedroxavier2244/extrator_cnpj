from __future__ import annotations

from fastapi import APIRouter

from app.core.metrics import get_metrics_store, get_uptime_seconds

router = APIRouter(prefix="/metrics", tags=["metrics"])


@router.get("", summary="Metricas basicas", description="Retorna contadores em memoria da API.")
def get_metrics() -> dict[str, float | int]:
    return get_metrics_store().snapshot(get_uptime_seconds())
