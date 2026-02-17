"""MedSigLIP wrapper — image embeddings and zero-shot wound classification."""

from __future__ import annotations

import hashlib
import logging
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

BURN_LABELS: list[str] = [
    "superficial partial-thickness burn",
    "deep partial-thickness burn",
    "full-thickness burn with eschar",
    "burn wound with active infection",
    "clean granulating burn wound",
    "re-epithelializing burn wound",
    "healed burn with hypertrophic scarring",
    "burn wound with graft integration",
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
        from transformers import SiglipModel, SiglipImageProcessor, SiglipTokenizer  # type: ignore[import-untyped]

        logger.info("Loading MedSigLIP model %s on %s ...", self.model_name, self.device)
        self._model = SiglipModel.from_pretrained(self.model_name).to(self.device)
        self._image_processor = SiglipImageProcessor.from_pretrained(self.model_name)
        self._tokenizer = SiglipTokenizer.from_pretrained(self.model_name)
        logger.info("MedSigLIP loaded.")

    # ---- Embedding ----------------------------------------------------------

    def get_embedding(self, image: Image.Image) -> np.ndarray:
        """Return a 1-D float32 embedding vector for the image."""
        if self.mock:
            seed = int.from_bytes(hashlib.md5(image.tobytes()).digest()[:4], "little")
            rng = np.random.default_rng(seed)
            return rng.standard_normal(768).astype(np.float32)

        inputs = self._image_processor(images=image, return_tensors="pt").to(self.device)
        with torch.no_grad():
            output = self._model.get_image_features(**inputs)
        # Handle both tensor and BaseModelOutputWithPooling returns
        if hasattr(output, "pooler_output"):
            features = output.pooler_output
        elif hasattr(output, "last_hidden_state"):
            features = output.last_hidden_state[:, 0]
        else:
            features = output
        return features.cpu().numpy().flatten().astype(np.float32)

    # ---- Zero-shot classification -------------------------------------------

    def zero_shot_classify(
        self, image: Image.Image, labels: list[str] | None = None
    ) -> dict[str, float]:
        """Zero-shot classification against wound-specific labels."""
        if labels is None:
            labels = WOUND_LABELS

        if self.mock:
            seed = int.from_bytes(hashlib.md5(image.tobytes()).digest()[:4], "little")
            rng = np.random.default_rng(seed + 1)  # +1 to differ from embedding
            raw = [float(rng.random()) for _ in labels]
            total = sum(raw)
            return {label: round(val / total, 4) for label, val in zip(labels, raw)}

        text_inputs = self._tokenizer(labels, return_tensors="pt", padding=True).to(self.device)
        image_inputs = self._image_processor(images=image, return_tensors="pt").to(self.device)
        inputs = {**text_inputs, **image_inputs}
        with torch.no_grad():
            outputs = self._model(**inputs)
        probs = outputs.logits_per_image.softmax(dim=1)[0]
        return {label: round(float(p), 4) for label, p in zip(labels, probs)}
