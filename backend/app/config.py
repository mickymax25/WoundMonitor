"""Application settings loaded from environment variables."""

from __future__ import annotations

from pydantic_settings import BaseSettings


def _detect_device() -> str:
    try:
        import torch
        return "cuda" if torch.cuda.is_available() else "cpu"
    except ImportError:
        return "cpu"


class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./data/woundchrono.db"
    DATA_DIR: str = "./data"
    UPLOAD_DIR: str = "./data/uploads"

    MEDGEMMA_MODEL: str = "google/medgemma-1.5-4b-it"
    MEDGEMMA_LORA_PATH: str = ""
    MEDSIGLIP_MODEL: str = "google/medsiglip-448"
    MEDASR_MODEL: str = "google/medasr"

    DEVICE: str = _detect_device()
    MOCK_MODELS: bool = False

    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://34.6.16.126:3000", "*"]

    model_config = {"env_prefix": "WOUNDCHRONO_", "env_file": ".env", "extra": "ignore"}


settings = Settings()
