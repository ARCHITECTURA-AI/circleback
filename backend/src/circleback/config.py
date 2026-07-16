"""Configuration management via pydantic-settings.

All required environment variables are declared here with validation.
Missing required vars raise a clear error at startup, not at first use.
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # ── Database ──────────────────────────────────────────────
    database_url: str = Field(
        ...,
        description="PostgreSQL connection string (asyncpg format)",
        examples=["postgresql+asyncpg://user:pass@localhost:5432/circleback"],
    )

    # ── API Keys ──────────────────────────────────────────────
    anthropic_api_key: str = Field(
        default="",
        description="Anthropic API key for Claude LLM calls",
    )

    # ── OAuth (Gmail) ─────────────────────────────────────────
    google_client_id: str = Field(default="", description="Google OAuth client ID")
    google_client_secret: str = Field(default="", description="Google OAuth client secret")

    # ── OAuth (Slack) ─────────────────────────────────────────
    slack_client_id: str = Field(default="", description="Slack OAuth client ID")
    slack_client_secret: str = Field(default="", description="Slack OAuth client secret")
    slack_signing_secret: str = Field(default="", description="Slack webhook signing secret")

    # ── Encryption ────────────────────────────────────────────
    token_encryption_key: str = Field(
        default="",
        description="Fernet key for encrypting OAuth tokens at rest",
    )

    # ── Session Auth ──────────────────────────────────────────
    session_secret_key: str = Field(
        default="",
        description="Secret key for signing session cookies (generate a random 32+ char string)",
    )

    # ── URLs ──────────────────────────────────────────────────
    base_url: str = Field(
        default="http://localhost:8000",
        description="Backend base URL (used for OAuth redirect URIs and HTTPS enforcement)",
    )
    frontend_url: str = Field(
        default="http://localhost:3000",
        description="Frontend base URL (used for CORS and post-OAuth redirects)",
    )

    # ── App ───────────────────────────────────────────────────
    app_name: str = Field(default="Circle Back")
    debug: bool = Field(default=False)
    log_level: str = Field(default="INFO")

    # ── LLM Cost Controls ─────────────────────────────────────
    llm_daily_cost_limit_usd: float = Field(
        default=10.0,
        description="Hard daily spend limit on LLM API calls",
    )

    # ── At-Risk Threshold ─────────────────────────────────────
    at_risk_hours_before_deadline: int = Field(
        default=24,
        description="Hours before deadline to transition commitment to at_risk",
    )


def get_settings() -> Settings:
    """Create and return a Settings instance.

    This is a factory function rather than a singleton so tests
    can easily override environment variables and get fresh config.
    """
    return Settings()  # type: ignore[call-arg]
