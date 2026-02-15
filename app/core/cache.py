from __future__ import annotations

import json
from threading import Lock
from typing import Any

from app.config import settings
from app.core.logging import get_logger
from app.core.metrics import increment_cache_hits_total, increment_cache_misses_total

logger = get_logger(__name__)

try:
    import redis  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    redis = None


class CacheBackend:
    def __init__(self) -> None:
        self.redis_url = (settings.REDIS_URL or "").strip()
        self.enabled = bool(self.redis_url and redis is not None)
        self.client = None

        if not self.redis_url:
            logger.info("cache.disabled", reason="empty_redis_url")
            return

        if redis is None:
            logger.warning("cache.disabled", reason="redis_module_not_installed")
            return

        try:
            self.client = redis.Redis.from_url(self.redis_url, decode_responses=True)
            self.client.ping()
        except Exception:
            logger.exception("cache.disabled", reason="redis_connection_failed")
            self.client = None
            self.enabled = False
            return

        logger.info("cache.enabled")

    def get(self, key: str) -> str | None:
        if not self.enabled or self.client is None:
            return None
        try:
            value = self.client.get(key)
            if value is None:
                increment_cache_misses_total()
                return None
            increment_cache_hits_total()
            return str(value)
        except Exception:
            logger.exception("cache.get_failed", key=key)
            return None

    def set(self, key: str, value: str, ttl: int) -> None:
        if not self.enabled or self.client is None:
            return
        try:
            self.client.setex(key, ttl, value)
        except Exception:
            logger.exception("cache.set_failed", key=key)

    def get_many(self, keys: list[str]) -> dict[str, str]:
        if not self.enabled or self.client is None or not keys:
            return {}
        try:
            values = self.client.mget(keys)
        except Exception:
            logger.exception("cache.get_many_failed", key_count=len(keys))
            return {}

        found: dict[str, str] = {}
        misses = 0
        for key, value in zip(keys, values):
            if value is not None:
                found[key] = str(value)
            else:
                misses += 1

        if found:
            increment_cache_hits_total(len(found))
        if misses:
            increment_cache_misses_total(misses)

        return found

    def set_many(self, mapping: dict[str, str], ttl: int) -> None:
        if not self.enabled or self.client is None or not mapping:
            return
        try:
            pipe = self.client.pipeline()
            for key, value in mapping.items():
                pipe.setex(key, ttl, value)
            pipe.execute()
        except Exception:
            logger.exception("cache.set_many_failed", key_count=len(mapping))

    @staticmethod
    def key(cnpj_basico_ou_completo: str) -> str:
        return f"cnpj:{cnpj_basico_ou_completo}"

    @staticmethod
    def serialize(value: dict[str, Any]) -> str:
        return json.dumps(value, ensure_ascii=True)

    @staticmethod
    def deserialize(value: str) -> dict[str, Any]:
        return json.loads(value)


_CACHE_SINGLETON: CacheBackend | None = None
_CACHE_LOCK = Lock()


def get_cache() -> CacheBackend:
    global _CACHE_SINGLETON
    if _CACHE_SINGLETON is None:
        with _CACHE_LOCK:
            if _CACHE_SINGLETON is None:
                _CACHE_SINGLETON = CacheBackend()
    return _CACHE_SINGLETON
