"""FastAPI application entry point for WoundChrono."""

from __future__ import annotations

import logging
import os
from contextlib import asynccontextmanager
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app import db
from app.agents.wound_agent import WoundAgent
from app.api.routes import router, set_agent
from app.config import settings
from app.models.medasr import MedASRWrapper
from app.models.medgemma import MedGemmaWrapper
from app.models.medsiglip import MedSigLIPWrapper

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Model loading
# ---------------------------------------------------------------------------

_medgemma: MedGemmaWrapper | None = None
_medsiglip: MedSigLIPWrapper | None = None
_medasr: MedASRWrapper | None = None


def load_models() -> WoundAgent:
    """Instantiate and load all three model wrappers, then build the agent."""
    global _medgemma, _medsiglip, _medasr

    mock = settings.MOCK_MODELS
    device = settings.DEVICE

    logger.info("Initializing models (mock=%s, device=%s).", mock, device)

    _medgemma = MedGemmaWrapper(
        settings.MEDGEMMA_MODEL, device, mock=mock, lora_path=settings.MEDGEMMA_LORA_PATH,
    )
    _medgemma.load()

    _medsiglip = MedSigLIPWrapper(settings.MEDSIGLIP_MODEL, device, mock=mock)
    _medsiglip.load()

    _medasr = MedASRWrapper(settings.MEDASR_MODEL, device, mock=mock)
    _medasr.load()

    agent = WoundAgent(medgemma=_medgemma, medsiglip=_medsiglip, medasr=_medasr, db=db)
    logger.info("All models loaded. WoundAgent ready.")
    return agent


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # Startup
    logger.info("Starting WoundChrono API.")
    db.init_db()
    db.migrate_patient_tokens()
    db.migrate_assessment_extras()
    db.migrate_assessment_images()
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

    agent = load_models()
    set_agent(agent)

    yield

    # Shutdown
    logger.info("Shutting down WoundChrono API.")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="WoundChrono API",
    version="0.1.0",
    description="Wound assessment system powered by Google HAI-DEF models.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api/v1")

# Ensure the upload directory exists so StaticFiles mount does not fail.
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=settings.UPLOAD_DIR), name="uploads")


# ---------------------------------------------------------------------------
# Health check
# ---------------------------------------------------------------------------

@app.get("/health")
def health_check() -> dict[str, str]:
    return {
        "status": "ok",
        "mock_mode": str(settings.MOCK_MODELS),
        "device": settings.DEVICE,
    }
