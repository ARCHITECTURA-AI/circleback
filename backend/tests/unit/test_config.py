"""Tests for configuration management.

TDD: These tests define the config contract.
- Required vars must be present or fail clearly.
- Optional vars have sensible defaults.
"""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from circleback.config import Settings, get_settings


class TestConfigLoadsFromEnv:
    """Config object loads required variables from environment."""

    def test_config_loads_database_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """DATABASE_URL is loaded from environment."""
        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")
        settings = Settings(_env_file=None)  # type: ignore[call-arg]
        assert settings.database_url == "postgresql+asyncpg://u:p@localhost/db"

    def test_config_loads_anthropic_key(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """ANTHROPIC_API_KEY is loaded from environment."""
        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-123")
        settings = Settings(_env_file=None)  # type: ignore[call-arg]
        assert settings.anthropic_api_key == "sk-test-123"

    def test_config_defaults_for_optional_fields(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Optional fields have sensible defaults."""
        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")
        # Ensure env vars aren't polluting the test
        monkeypatch.delenv("DEBUG", raising=False)
        monkeypatch.delenv("LOG_LEVEL", raising=False)
        monkeypatch.delenv("LLM_DAILY_COST_LIMIT_USD", raising=False)
        monkeypatch.delenv("AT_RISK_HOURS_BEFORE_DEADLINE", raising=False)
        settings = Settings(_env_file=None)  # type: ignore[call-arg]
        assert settings.app_name == "Circle Back"
        assert settings.debug is False
        assert settings.log_level == "INFO"
        assert settings.llm_daily_cost_limit_usd == 10.0
        assert settings.at_risk_hours_before_deadline == 24


class TestConfigFailsOnMissing:
    """Config raises clear errors when required vars are missing."""

    def test_config_fails_on_missing_database_url(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Config raises ValidationError when DATABASE_URL is missing."""
        # Clear any existing DATABASE_URL
        monkeypatch.delenv("DATABASE_URL", raising=False)
        # Also clear any .env file influence
        with pytest.raises(ValidationError) as exc_info:
            Settings(_env_file=None)  # type: ignore[call-arg]
        # The error should mention database_url
        assert "database_url" in str(exc_info.value).lower()


class TestGetSettings:
    """get_settings() factory function."""

    def test_get_settings_returns_settings_instance(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """get_settings() returns a Settings instance."""
        monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@localhost/db")
        settings = get_settings()
        assert isinstance(settings, Settings)
