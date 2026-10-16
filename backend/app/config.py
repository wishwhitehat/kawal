"""Runtime configuration, read from environment variables (see .env.example)."""

from functools import lru_cache

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

_GLOBAL = {"check": 150, "grounding": 60, "live": 25, "tts": 40, "ask": 60, "bulletin": 8}
_USER = {"check": 20, "live": 5, "tts": 10, "ask": 15, "bulletin": 3}
_IP = {"check": 40, "live": 10, "tts": 20, "ask": 30, "bulletin": 5}


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

    # ---- abuse & cost controls (see app/guard.py) --------------------------------
    # Require a Firebase App Check token (reCAPTCHA Enterprise) on every AI call.
    appcheck_required: bool = False
    rate_limit_per_minute: int = 12
    # Daily ceilings. GLOBAL caps bound the worst-case daily model spend; user and
    # IP caps stop one caller from exhausting them. JSON in env, e.g.
    # GLOBAL_DAILY='{"check":150,...}'
    global_daily: dict[str, int] = _GLOBAL
    user_daily: dict[str, int] = _USER
    ip_daily: dict[str, int] = _IP

    # Context trimming: what we are willing to send to a model per request.
    max_text_chars: int = 4000
    max_files: int = 2
    max_image_mb: float = 4
    max_audio_mb: float = 3
    max_pdf_mb: float = 2
    live_max_seconds: int = 150
    live_score_interval: float = 3.0
    live_max_scores: int = 40
    live_window_chars: int = 3000
    bulletin_cache_minutes: int = 60
    check_cache_hours: int = 24

    # Budget circuit breaker (Pub/Sub push from Cloud Billing budgets).
    budget_push_audience: str = ""
    budget_push_sa: str = ""
    breaker_ratio: float = 1.0

    @field_validator("global_daily", "user_daily", "ip_daily", mode="before")
    @classmethod
    def _merge_defaults(cls, v, info):
        """A partial override (e.g. only "check") must never drop the other caps."""
        defaults = {"global_daily": _GLOBAL, "user_daily": _USER, "ip_daily": _IP}[info.field_name]
        return {**defaults, **(v or {})}

    @property
    def origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
