from __future__ import annotations

from functools import lru_cache

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
    CORS_ORIGINS: list[str] = ["*"]

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
