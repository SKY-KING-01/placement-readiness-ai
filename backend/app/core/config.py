from functools import lru_cache
from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(ROOT / ".env", ROOT / "backend/.env"), extra="ignore")
    database_url: str = "postgresql+psycopg://localhost/placement_readiness"
    jwt_secret_key: SecretStr = SecretStr("")
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"
    app_env: str = "development"
    openai_api_key: SecretStr = SecretStr("")
    openai_model: str = ""
    openai_timeout_seconds: float = Field(default=30, gt=0, le=120)
    openai_max_retries: int = Field(default=2, ge=0, le=5)
    openai_input_price_per_million: float | None = Field(default=None, ge=0)
    openai_output_price_per_million: float | None = Field(default=None, ge=0)
    python_execution_enabled: bool = False
    model_artifact_dir: Path = ROOT / "ml/artifacts"
    min_cohort: int = Field(default=5, ge=5)
    synthetic_demo_predictions: bool = False


@lru_cache
def settings() -> Settings:
    return Settings()
