"""Application configuration loaded from environment / .env via Pydantic Settings.

Sensitive values (tokens, API keys, api_id/api_hash) are ONLY read from the
environment. They are never hardcoded here.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # --- Telegram ---
    telegram_bot_token: str = Field(default="", alias="TELEGRAM_BOT_TOKEN")
    telegram_owner_id: int = Field(default=0, alias="TELEGRAM_OWNER_ID")

    # --- Cloudflare ---
    cloudflare_api_token: str = Field(default="", alias="CLOUDFLARE_API_TOKEN")
    cloudflare_account_id: str = Field(default="", alias="CLOUDFLARE_ACCOUNT_ID")
    default_destination_email: str = Field(default="", alias="DEFAULT_DESTINATION_EMAIL")

    # --- Database ---
    database_url: str = Field(
        default="sqlite+aiosqlite:///data/bot.db", alias="DATABASE_URL"
    )

    # --- Local Bot API + Redis ---
    bot_api_root: Optional[str] = Field(default=None, alias="BOT_API_ROOT")
    telegram_api_id: Optional[str] = Field(default=None, alias="TELEGRAM_API_ID")
    telegram_api_hash: Optional[str] = Field(default=None, alias="TELEGRAM_API_HASH")
    redis_url: Optional[str] = Field(default=None, alias="REDIS_URL")

    # --- Premium emoji ---
    use_premium_emoji: bool = Field(default=False, alias="USE_PREMIUM_EMOJI")

    # --- Behaviour / limits ---
    name_reservation_minutes: int = Field(default=10, alias="NAME_RESERVATION_MINUTES")
    max_generation_attempts: int = Field(default=100, alias="MAX_GENERATION_ATTEMPTS")
    domain_page_size: int = Field(default=20, alias="DOMAIN_PAGE_SIZE")
    email_page_size: int = Field(default=20, alias="EMAIL_PAGE_SIZE")

    def validate_required(self) -> list[str]:
        """Return a list of human-readable problems with the configuration."""
        problems: list[str] = []
        if not self.telegram_bot_token:
            problems.append("TELEGRAM_BOT_TOKEN belum diisi")
        if not self.telegram_owner_id:
            problems.append("TELEGRAM_OWNER_ID belum diisi")
        if not self.cloudflare_api_token:
            problems.append("CLOUDFLARE_API_TOKEN belum diisi")
        if not self.default_destination_email:
            problems.append("DEFAULT_DESTINATION_EMAIL belum diisi")
        return problems

    @property
    def normalized_bot_api_root(self) -> Optional[str]:
        if self.bot_api_root and self.bot_api_root.strip():
            return self.bot_api_root.strip().rstrip("/")
        return None


@lru_cache
def get_settings() -> Settings:
    return Settings()
