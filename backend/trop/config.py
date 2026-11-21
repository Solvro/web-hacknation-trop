"""Settings from env / .env (repo root). Contract: every module reads config ONLY through `settings`."""
from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

REPO = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=(str(REPO / ".env"),), extra="ignore")

    # mode
    trop_mode: str = "live"                 # live | offline (no network, cached model outputs only) | mock (API fixtures)
    trop_capture: str | None = None         # off | sandbox | local; None = sandbox when trop_mode=live else off (URL input -> board-13 job.error)
    trop_replay: bool = False               # SSE endpoints serve recorded streams by default

    # storage
    database_url: str = "postgresql://redpill:redpill_dev@127.0.0.1:55432/redpill"
    redis_url: str = "redis://127.0.0.1:56379/0"
    data_dir: Path = REPO / "data"
    artifact_dir: Path = REPO / "data" / "artifacts"
    cache_dir: Path = REPO / "data" / "cache"          # model + enrichment cache (sha256-keyed)
    models_dir: Path = REPO / "data" / "models"        # face gallery index etc.
    replay_dir: Path = REPO / "data" / "replay"        # recorded SSE streams (demo)

    # LLM / VLM
    gemini_api_key: str | None = None
    gemini_flash_model: str = "gemini-flash-latest"
    gemini_pro_model: str = "gemini-pro-latest"
    gemini_asr_model: str = "gemini-3.5-transcribe"
    openrouter_api_key: str | None = None
    openrouter_vlm_model: str = "qwen/qwen3.6-35b-a3b"
    openrouter_llm_model: str = "qwen/qwen3.8-27b"
    anthropic_api_key: str | None = None
    llm_budget_usd: float = 30.0

    # sources
    meta_access_token: str | None = None
    meta_app_id: str | None = None
    meta_app_secret: str | None = None
    urlscan_api_key: str | None = None
    ipinfo_token: str | None = None
    certspotter_api_key: str | None = None
    google_cloud_project: str | None = None
    wikimedia_ua: str | None = None

    # api
    api_base_path: str = "/api/v1"
    cors_origins: str = "*"


settings = Settings()
