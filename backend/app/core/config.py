"""Application configuration via environment variables."""
from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # App
    app_name: str = "Ecommerce Brain"
    debug: bool = False
    api_v1_prefix: str = "/api"

    # Database
    database_url: str = Field(
        default="postgresql://brain:brain@postgres:5432/brain",
        description="Asyncpg-compatible DSN",
    )

    # Auth
    jwt_secret: str = Field(default="change_me_in_production_min_32_chars")
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440

    # LLM
    llm_provider: Literal["minimax", "anthropic", "openai"] = "minimax"
    minimax_api_key: str = ""
    minimax_base_url: str = "https://api.minimax.io/v1"
    minimax_model: str = "MiniMax-M3"
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    llm_timeout_seconds: int = 60

    # n8n (existente, NO se levanta aquí)
    n8n_api_url: str = "http://host.docker.internal:5678"
    n8n_api_key: str = ""

    # Evolution API (fase 4)
    evolution_api_url: str = "http://evolution:8080"
    evolution_api_key: str = ""

    # Cálculos
    gateway_fee_pct: float = 0.035
    return_cost_est_pct: float = 0.05

    # CORS
    cors_origins: list[str] = ["http://localhost:3040", "http://127.0.0.1:3040"]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()