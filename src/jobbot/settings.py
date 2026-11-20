from __future__ import annotations

import os
from pathlib import Path
from typing import Annotated, Literal

from dotenv import dotenv_values
from pydantic import BaseModel, SecretStr, field_validator
from pydantic_settings import (
    BaseSettings,
    NoDecode,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
)

Env = Literal["dev", "test", "prod"]


class Limits(BaseModel):
    companies: int | None = None
    jobs: int | None = None
    jobs_per_company: int | None = None
    max_roles: int = 25
    max_prospects: int = 5


class HttpSettings(BaseModel):
    requests_per_second_per_host: float = 5
    max_retries: int = 4
    timeout_seconds: float = 30


def config_dir() -> Path:
    return Path(os.environ.get("JOBBOT_CONFIG_DIR", Path.cwd()))


def current_env() -> Env:
    env = os.environ.get("JOBBOT_ENV") or dotenv_values(config_dir() / ".env").get("JOBBOT_ENV") or "dev"
    if env not in ("dev", "test", "prod"):
        raise ValueError(f"JOBBOT_ENV must be dev, test or prod, got {env!r}")
    return env  # type: ignore[return-value]


def normalize_db_url(url: str) -> str:
    """Supabase hands out `postgresql://` URLs; SQLAlchemy needs the psycopg 3 driver named."""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix) :]
    return url


class Settings(BaseSettings):
    """Precedence, highest first: constructor kwargs (command flags), environment variables,
    `.env`, `config.<env>.toml`, `config.toml`."""

    model_config = SettingsConfigDict(
        env_prefix="JOBBOT_",
        env_nested_delimiter="__",
        env_file=".env",
        extra="ignore",
    )

    env: Env = "dev"
    database_url: str = "postgresql+psycopg://postgres:postgres@localhost:5432/jobbot_dev"
    database_url_direct: str | None = None

    llm_budget_usd_per_run: float = 1.00
    max_paid_lookups_per_run: int = 0

    allowed_emails: Annotated[list[str], NoDecode] = []
    email_from: str = "Shortlist <digest@mail.example.com>"
    email_test_to: str | None = None
    resend_api_key: SecretStr | None = None

    openai_api_key: SecretStr | None = None
    anthropic_api_key: SecretStr | None = None

    fixtures_dir: Path = Path("fixtures")
    previews_dir: Path = Path("previews")
    log_format: Literal["console", "json"] = "console"

    limits: Limits = Limits()
    http: HttpSettings = HttpSettings()

    @field_validator("database_url", "database_url_direct")
    @classmethod
    def _normalize_url(cls, v: str | None) -> str | None:
        return normalize_db_url(v) if v else None

    @field_validator("allowed_emails", mode="before")
    @classmethod
    def _split_emails(cls, v: object) -> object:
        if isinstance(v, str):
            return [e.strip().lower() for e in v.split(",") if e.strip()]
        if isinstance(v, list):
            return [str(e).strip().lower() for e in v if str(e).strip()]
        return v

    @field_validator("email_test_to")
    @classmethod
    def _empty_is_none(cls, v: str | None) -> str | None:
        return v or None

    @property
    def migration_url(self) -> str:
        return self.database_url_direct or self.database_url

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        base = config_dir()
        toml = TomlConfigSettingsSource(
            settings_cls,
            toml_file=[base / "config.toml", base / f"config.{current_env()}.toml"],
            deep_merge=True,
        )
        return (init_settings, env_settings, dotenv_settings, toml)


def load_settings(**overrides: object) -> Settings:
    return Settings(**overrides)  # type: ignore[arg-type]
