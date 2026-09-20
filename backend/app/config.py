"""Validated application settings with a stable, backend-relative env path."""

from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="AGENTGATE_",
        env_file=BACKEND_DIR / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = Field(default="AgentGate", min_length=1)
    environment: Literal["development", "test", "production"] = "development"
    cors_origins: list[str] = Field(
        default_factory=lambda: [
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ]
    )
    # Vercel gives every preview deployment its own hostname, so the browser
    # origin cannot be enumerated ahead of time. A regex keeps the allowlist
    # closed over a known suffix instead of degrading to "*".
    cors_origin_regex: str | None = None
    # Policies live outside the backend package so they read as the product's
    # authority document, not as application code that happens to be data.
    policy_dir: Path = Field(default_factory=lambda: BACKEND_DIR.parent / "policies")
    policy_store_path: Path = Field(default_factory=lambda: BACKEND_DIR / "data" / "policies.json")
    ai_api_key: str | None = None
    ai_base_url: str = "https://api.openai.com/v1"
    ai_model: str = "gpt-4o-mini"
