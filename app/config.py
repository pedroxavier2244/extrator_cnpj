from __future__ import annotations

import json
from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str
    RAW_DATA_PATH: str = "data/raw"
    STAGING_PATH: str = "data/staging"
    PROCESSED_PATH: str = "data/processed"
    BATCH_SIZE: int = 50000
    REDIS_URL: str = ""
    CACHE_TTL_SECONDS: int = 86400
    BATCH_MAX_SIZE: int = 1000
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 40
    DB_POOL_TIMEOUT: int = 30
    LOG_LEVEL: str = "INFO"
    API_V1_PREFIX: str = "/api/v1"
    APP_NAME: str = "Sistema CNPJ"
    ETL_HASH_ALGORITHM: str = "sha256"
    ENVIRONMENT: str = "production"
    TRUST_PROXY: bool = False
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:5500"]
    API_KEYS: list[str] = []

    @field_validator("CORS_ORIGINS", "API_KEYS", mode="before")
    @classmethod
    def parse_csv_or_json_list(cls, value: object) -> list[str]:
        if value is None:
            return []

        if isinstance(value, str):
            raw = value.strip()
            if not raw:
                return []

            if raw.startswith("["):
                try:
                    parsed = json.loads(raw)
                    if isinstance(parsed, list):
                        return [str(item).strip() for item in parsed if str(item).strip()]
                except json.JSONDecodeError:
                    pass

            return [item.strip() for item in raw.split(",") if item.strip()]

        if isinstance(value, (list, tuple, set)):
            return [str(item).strip() for item in value if str(item).strip()]

        return [str(value).strip()] if str(value).strip() else []

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
