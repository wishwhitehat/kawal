"""Runtime configuration, read from environment variables (see .env.example)."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    project_id: str = ""
    # Gemini 3.8 Flash is served from the global endpoint; Live is regional.
    gemini_location: str = "global"
    live_location: str = "us-central1"

    model_flash: str = "gemini-3.8-flash"
    # Used automatically if the primary model is out of capacity (HTTP 429/503).
    model_fallback: str = "gemini-3.5-flash"
    model_lite: str = "gemini-3.5-flash-lite"
    model_live: str = "gemini-3.8-live"
    model_embed: str = "gemini-embedding-2"
    model_tts: str = "gemini-3.8-flash-tts"
    embed_dim: int = 768

    firestore_database: str = "(default)"

    # Comma-separated list of browser origins allowed to call the API.
    allowed_origins: str = "http://localhost:5173"
    # When false (local dev only) requests without a Firebase ID token are accepted.
    auth_required: bool = True
    # Secret used to HMAC indicators (phone numbers, accounts, URLs) before storage.
    # Injected from Secret Manager on Cloud Run; never committed.
    indicator_pepper: str = "dev-only-pepper"

    max_upload_mb: int = 8
    rate_limit_per_minute: int = 20
    live_max_seconds: int = 600

    @property
    def origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
