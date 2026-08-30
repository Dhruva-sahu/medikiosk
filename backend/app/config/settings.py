"""Application configuration loaded from environment variables.

Centralised so individual modules don't have to read os.environ directly.
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from typing import List

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Strongly-typed application settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # Server
    app_name: str = "Swasthya Setu"
    app_env: str = "development"
    app_port: int = 8000
    app_host: str = "0.0.0.0"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # Database
    database_url: str = "sqlite:///./medikiosk.db"

    # Security
    jwt_secret: str = "medikiosk-dev-secret-change-me"
    jwt_algorithm: str = "HS256"
    jwt_expires_minutes: int = 480

    # AI
    ai_mode: str = "mock"
    ai_provider: str = "mock"
    openai_api_key: str = ""
    openai_model: str = "gpt-4o-mini"
    gemini_api_key: str = ""
    gemini_model: str = "gemini-1.5-flash"
    anthropic_api_key: str = ""
    claude_api_key: str = ""
    claude_model: str = "claude-3-5-sonnet-20240620"

    # OCR
    ocr_provider: str = "mock"

    # Speech
    speech_provider: str = "mock"
    bhashini_api_key: str = ""

    # Integrations
    abdm_base_url: str = ""
    abdm_client_id: str = ""
    abdm_client_secret: str = ""
    fhir_base_url: str = ""
    his_base_url: str = ""

    # Storage
    upload_dir: str = "./uploads/documents"
    max_upload_bytes: int = 10 * 1024 * 1024

    @property
    def cors_origin_list(self) -> List[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def upload_path(self) -> Path:
        p = Path(self.upload_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p


@lru_cache()
def get_settings() -> Settings:
    return Settings()
