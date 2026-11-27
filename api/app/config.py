"""Application settings. All model and provider choices live here, never inline in nodes."""

from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

LLMProvider = Literal["mock", "anthropic", "google"]

API_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = API_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=API_DIR / ".env", extra="ignore")

    app_env: Literal["local", "test", "production"] = "local"
    database_url: str = "postgresql://postgres:postgres@127.0.0.1:54322/postgres"
    supabase_url: str = "http://127.0.0.1:54321"
    supabase_service_role_key: str = ""
    supabase_jwt_secret: str = ""
    journal_encryption_key: str = ""
    web_origin: str = "http://localhost:5173"

    # Models: provider per tier, model id per tier.
    llm_provider_main: LLMProvider = "mock"
    llm_model_main: str = "claude-sonnet-5-5"
    llm_provider_fast: LLMProvider = "mock"
    llm_model_fast: str = "claude-haiku-5-5"
    embedding_provider: Literal["mock", "google"] = "mock"
    embedding_dim: int = 768
    anthropic_api_key: str = ""
    google_api_key: str = ""

    elevenlabs_api_key: str = ""
    tts_mode: Literal["mock", "flash", "v3"] = "mock"
    image_mode: Literal["placeholder", "library", "generate"] = "placeholder"
    ocr_mode: Literal["mock", "google"] = "mock"
    storage_backend: Literal["local", "r2"] = "local"
    local_storage_dir: Path = API_DIR / ".data" / "media"
    r2_account_id: str = ""
    r2_access_key_id: str = ""
    r2_secret_access_key: str = ""
    r2_bucket: str = "grove-media"

    langsmith_tracing: bool = False
    traditions_dir: Path = REPO_ROOT / "traditions"

    @model_validator(mode="after")
    def _keys_present_for_real_services(self) -> "Settings":
        """Fail fast, naming the missing variable (never printing values)."""
        missing: list[str] = []
        providers = {self.llm_provider_main, self.llm_provider_fast}
        if "anthropic" in providers and not self.anthropic_api_key:
            missing.append("ANTHROPIC_API_KEY")
        needs_google = (
            "google" in providers
            or self.embedding_provider == "google"
            or self.ocr_mode == "google"
            or self.image_mode == "generate"
        )
        if needs_google and not self.google_api_key:
            missing.append("GOOGLE_API_KEY")
        if self.tts_mode != "mock" and not self.elevenlabs_api_key:
            missing.append("ELEVENLABS_API_KEY")
        if self.storage_backend == "r2":
            for name in ("r2_account_id", "r2_access_key_id", "r2_secret_access_key"):
                if not getattr(self, name):
                    missing.append(name.upper())
        if missing:
            raise ValueError(f"Missing required settings for selected modes: {', '.join(missing)}")
        return self

    def adapter_modes(self) -> dict[str, str]:
        return {
            "llm_main": self.llm_provider_main,
            "llm_fast": self.llm_provider_fast,
            "embeddings": self.embedding_provider,
            "tts": self.tts_mode,
            "images": self.image_mode,
            "ocr": self.ocr_mode,
            "storage": self.storage_backend,
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
