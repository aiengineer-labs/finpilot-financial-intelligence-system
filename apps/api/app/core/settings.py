from functools import lru_cache
from typing import Literal

from pydantic import AnyHttpUrl, Field, SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../../.env"), env_file_encoding="utf-8", extra="ignore"
    )

    environment: Literal["development", "test", "production"] = "development"
    database_url: str = "postgresql+asyncpg://finpilot:finpilot@localhost:5432/finpilot"
    session_secret: SecretStr = Field(min_length=32)
    access_token_minutes: int = Field(default=30, ge=5, le=1440)
    allowed_origins: list[str] = ["http://localhost:3000"]
    mesh_api_key: SecretStr | None = None
    mesh_base_url: AnyHttpUrl = AnyHttpUrl("https://api.meshapi.ai/v1")
    mesh_model: str = ""
    mesh_timeout_seconds: float = Field(default=20, gt=0, le=60)

    @field_validator("mesh_base_url")
    @classmethod
    def enforce_mesh_endpoint(cls, value: AnyHttpUrl) -> AnyHttpUrl:
        if value.host != "api.meshapi.ai" or value.scheme != "https":
            raise ValueError("all model inference must use https://api.meshapi.ai")
        return value

    @field_validator("session_secret")
    @classmethod
    def reject_example_secret(cls, value: SecretStr) -> SecretStr:
        if value.get_secret_value() in {"change-me", "secret", "changeme"}:
            raise ValueError("SESSION_SECRET must not use an example value")
        return value


@lru_cache
def get_settings() -> Settings:
    return Settings()
