from __future__ import annotations

from functools import lru_cache

try:
    from pydantic_settings import BaseSettings, SettingsConfigDict
except ImportError:  # pydantic v1 fallback
    from pydantic import BaseSettings

    SettingsConfigDict = None


class Settings(BaseSettings):
    DATABASE_URL: str
    RAW_DATA_PATH: str = "data/raw"
    STAGING_PATH: str = "data/staging"
    PROCESSED_PATH: str = "data/processed"
    BATCH_SIZE: int = 50000
    LOG_LEVEL: str = "INFO"
    API_V1_PREFIX: str = "/api/v1"
    APP_NAME: str = "Sistema CNPJ"
    ETL_HASH_ALGORITHM: str = "sha256"

    if SettingsConfigDict is not None:
        model_config = SettingsConfigDict(
            env_file=".env",
            env_file_encoding="utf-8",
            case_sensitive=False,
            extra="ignore",
        )
    else:
        class Config:
            env_file = ".env"
            env_file_encoding = "utf-8"
            case_sensitive = False


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
