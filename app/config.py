"""Environment-based configuration. No secrets in code."""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


ROOT_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    """Runtime settings loaded from environment / .env."""

    model_config = SettingsConfigDict(
        env_file=str(ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    demo_mode: bool = True
    secret_key: str = "dev-only-set-SECRET_KEY"

    ai_api_key: str = ""
    ai_base_url: str = "https://api.openai.com/v1"
    ai_model: str = ""

    api_host: str = "127.0.0.1"
    api_port: int = 8000
    flask_host: str = "127.0.0.1"
    flask_port: int = 5000
    api_base_url: str = "http://127.0.0.1:8000"

    database_url: str = "sqlite:///./data/reem.db"

    max_agent_loops: int = 3
    payment_retry_limit: int = 3
    circuit_breaker_threshold: int = 3
    rate_limit_per_claim: int = 40

    upload_dir: str = str(ROOT_DIR / "uploads")
    data_dir: str = str(ROOT_DIR / "data")

    estimated_cost_per_1k_tokens: float = 0.002

    def ai_available(self) -> bool:
        """True only when a live model is configured and demo mode is off."""
        return (
            not self.demo_mode
            and bool(self.ai_api_key.strip())
            and bool(self.ai_model.strip())
        )


@lru_cache
def get_settings() -> Settings:
    return Settings()
