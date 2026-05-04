from functools import cached_property
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    eptr_dotenv_path: str = ".env"
    eptr_tgt_path: str = "."

    # When set (non-empty), /power-plants routes require header: X-API-Key: <value>
    api_key: str | None = None

    # Comma-separated origins (e.g. https://app.example.com). Empty → localhost regex only.
    cors_allow_origins: str = ""

    def cors_allow_origins_list(self) -> list[str]:
        raw = (self.cors_allow_origins or "").strip()
        if not raw:
            return []
        return [p.strip() for p in raw.split(",") if p.strip()]

    @cached_property
    def eptr_dotenv_resolved(self) -> Path:
        return Path(self.eptr_dotenv_path).resolve()
