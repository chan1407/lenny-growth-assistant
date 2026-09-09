import os
from pathlib import Path

from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")


class Settings:
    def __init__(self) -> None:
        self.database_url = os.getenv("DATABASE_URL")
        self.llm_provider = os.getenv("LLM_PROVIDER", "ollama").strip().lower()
        fallback_provider = os.getenv("LLM_FALLBACK_PROVIDER")
        self.llm_fallback_provider = fallback_provider.strip().lower() if fallback_provider else None
        self.ollama_model = os.getenv("OLLAMA_MODEL", "llama3.2:3b")
        self.ollama_base_url = os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434")
        self.ollama_timeout_seconds = float(os.getenv("OLLAMA_TIMEOUT_SECONDS", "120"))
        self.ollama_health_timeout_seconds = float(os.getenv("OLLAMA_HEALTH_TIMEOUT_SECONDS", "3"))
        self.database_connect_timeout_seconds = int(os.getenv("DATABASE_CONNECT_TIMEOUT_SECONDS", "5"))
        self.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
        self.anthropic_model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-20250514")

    @property
    def database_configured(self) -> bool:
        return bool(self.database_url)

    @property
    def ollama_configured(self) -> bool:
        return bool(self.ollama_model and self.ollama_base_url)

    @property
    def anthropic_configured(self) -> bool:
        return bool(self.anthropic_api_key and self.anthropic_model)


settings = Settings()
