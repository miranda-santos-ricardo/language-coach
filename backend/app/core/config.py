import os
from dotenv import load_dotenv
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict

load_dotenv()

class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "AI Language & Professional Communication Coach"
    app_version: str = "0.1.0"
    environment: str = "development"
    database_url: str = (
        "postgresql+psycopg://"
        "admin:admin123@192.168.2.38:5434/language_coach"
    )

    cors_origins: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://192.168.2.25:5173",
        "*"
    ]

    openai_api_key: str | None = None
    openai_stt_model: str = "gpt-transcribe"
    openai_stt_timeout_seconds: float = 30.0


@lru_cache
def get_settings() -> Settings:
    return Settings()
