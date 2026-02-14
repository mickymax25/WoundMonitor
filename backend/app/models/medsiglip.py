"""MedSigLIP wrapper — image embeddings and zero-shot wound classification."""

from __future__ import annotations

import logging
import random
from typing import Any

import numpy as np
from PIL import Image

try:
    import torch
except ImportError:
    torch = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

WOUND_LABELS: list[str] = [
    "healthy granulating wound",
    "infected wound with purulent discharge",
    "necrotic wound tissue",
    "wound with fibrin slough",
    "epithelializing wound edge",
    "dry wound bed",
    "wound with excessive exudate",
    "wound with undermined edges",
]


class MedSigLIPWrapper:
    """Thin wrapper around the MedSigLIP vision-language model."""

    def __init__(self, model_name: str, device: str, *, mock: bool = False) -> None:
        self.model_name = model_name
        self.device = device
        self.mock = mock
        self._model: Any = None
        self._processor: Any = None

    def load(self) -> None:
        if self.mock:
            logger.info("MedSigLIP running in MOCK mode.")
            return
        from transformers import AutoModel, AutoProcessor  # type: ignore[import-untyped]

        logger.info("Loading MedSigLIP model %s on %s ...", self.model_name, self.device)
        self._model = AutoModel.from_pretrained(self.model_name).to(self.device)
        self._processor = AutoProcessor.from_pretrained(self.model_name)
        logger.info("MedSigLIP loaded.")

    # ---- Embedding ----------------------------------------------------------

    def get_embedding(self, image: Image.Image) -> np.ndarray:
        """Return a 1-D float32 embedding vector for the image."""
        if self.mock:
            return np.random.default_rng().standard_normal(768).astype(np.float32)

        inputs = self._processor(images=image, return_tensors="pt").to(self.device)
        with torch.no_grad():
            features = self._model.get_image_features(**inputs)
        return features.cpu().numpy().flatten().astype(np.float32)

    # ---- Zero-shot classification -------------------------------------------

    def zero_shot_classify(
        self, image: Image.Image, labels: list[str] | None = None
    ) -> dict[str, float]:
        """Zero-shot classification against wound-specific labels."""
        if labels is None:
            labels = WOUND_LABELS

        if self.mock:
            raw = [random.random() for _ in labels]
            total = sum(raw)
            return {label: round(val / total, 4) for label, val in zip(labels, raw)}

        inputs = self._processor(
            text=labels, images=image, return_tensors="pt", padding=True
        ).to(self.device)
        with torch.no_grad():
            outputs = self._model(**inputs)
        probs = outputs.logits_per_image.softmax(dim=1)[0]
        return {label: round(float(p), 4) for label, p in zip(labels, probs)}
