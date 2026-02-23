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

        # Force CPU to keep GPU VRAM free for MedGemma + LoRA
        self._infer_device = "cpu"
        logger.info("Loading MedSigLIP model %s on %s (GPU reserved for MedGemma) ...", self.model_name, self._infer_device)
        self._model = SiglipModel.from_pretrained(
            self.model_name, torch_dtype=torch.float32,
        ).to(self._infer_device)
        self._image_processor = SiglipImageProcessor.from_pretrained(self.model_name)
        self._tokenizer = SiglipTokenizer.from_pretrained(self.model_name)
        logger.info("MedSigLIP loaded on CPU.")

    # ---- Embedding ----------------------------------------------------------

    def get_embedding(self, image: Image.Image) -> np.ndarray:
        """Return a 1-D float32 embedding vector for the image."""
        if self.mock:
            seed = int.from_bytes(hashlib.md5(image.tobytes()).digest()[:4], "little")
            rng = np.random.default_rng(seed)
            return rng.standard_normal(768).astype(np.float32)

        inputs = self._image_processor(images=image, return_tensors="pt").to(self._infer_device)
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

        text_inputs = self._tokenizer(labels, return_tensors="pt", padding=True).to(self._infer_device)
        image_inputs = self._image_processor(images=image, return_tensors="pt").to(self._infer_device)
        inputs = {**text_inputs, **image_inputs}
        with torch.no_grad():
            outputs = self._model(**inputs)
        probs = outputs.logits_per_image.softmax(dim=1)[0]
        return {label: round(float(p), 4) for label, p in zip(labels, probs)}

    # ---- Per-dimension TIME scoring -----------------------------------------

    # Each dimension has 3 labels: good (score=1.0), moderate (0.5), bad (0.0).
    # SigLIP classifies between these 3 for each dimension independently.
    _TIME_LABELS: dict[str, list[tuple[str, float]]] = {
        "tissue": [
            ("wound with healthy pink granulation tissue and clean wound bed", 1.0),
            ("wound with yellow fibrinous slough partially covering the wound bed", 0.4),
            ("wound with black necrotic eschar and devitalized tissue", 0.0),
        ],
        "inflammation": [
            ("wound with clean healthy surrounding skin and no signs of infection", 1.0),
            ("wound with mild redness and warmth around the wound edges", 0.5),
            ("wound with severe infection cellulitis and purulent discharge", 0.0),
        ],
        "moisture": [
            ("wound with moist glistening wound bed and balanced moisture", 1.0),
            ("wound that appears dry with inadequate moisture", 0.35),
            ("wound with heavy exudate and macerated periwound skin", 0.0),
        ],
        "edge": [
            ("wound with advancing epithelial edges and active contraction", 1.0),
            ("wound with attached but non-advancing wound edges", 0.45),
            ("wound with rolled undermined wound edges and no epithelial advancement", 0.0),
        ],
    }

    def classify_time_dimensions(self, image: Image.Image) -> dict[str, float]:
        """Score each TIME dimension using logit difference between good/bad labels.

        For each dimension, computes raw SigLIP logits for a "healthy" and a
        "pathological" description. The logit difference (good - bad) is converted
        to a score in [0, 1] via a calibrated sigmoid.

        Returns: {"tissue": float, "inflammation": float, "moisture": float, "edge": float}
        """
        if self.mock:
            seed = int.from_bytes(hashlib.md5(image.tobytes()).digest()[:4], "little")
            rng = np.random.default_rng(seed + 2)
            return {
                dim: round(float(rng.random()), 2)
                for dim in ("tissue", "inflammation", "moisture", "edge")
            }

        import math

        image_inputs = self._image_processor(images=image, return_tensors="pt").to(self._infer_device)

        # Score each dimension by comparing good vs bad label
        logits: list[float] = []  # [good_T, good_I, good_M, good_E, bad_T, bad_I, bad_M, bad_E]
        dims = list(self._TIME_LABELS.keys())
        for dim in dims:
            labels_pair = [self._TIME_LABELS[dim][0][0], self._TIME_LABELS[dim][-1][0]]
            text_inputs = self._tokenizer(labels_pair, return_tensors="pt", padding=True).to(self._infer_device)
            inputs = {**text_inputs, **image_inputs}
            with torch.no_grad():
                outputs = self._model(**inputs)
            # logits_per_image shape: (1, 2) — [good_logit, bad_logit]
            logits.append(float(outputs.logits_per_image[0, 0]))  # good
            logits.append(float(outputs.logits_per_image[0, 1]))  # bad

        results: dict[str, float] = {}
        # Sigmoid calibration parameters
        k = 10.0     # steepness: higher = more extreme scores
        bias = 0.15  # shift sigmoid left: makes scores cluster lower (more clinical)

        deltas = []
        for i, dim in enumerate(dims):
            good_logit = logits[i * 2]      # even indices: good
            bad_logit = logits[i * 2 + 1]   # odd indices: bad
            delta = good_logit - bad_logit - bias
            deltas.append(delta + bias)  # log original delta
            # Sigmoid mapping: delta > 0 means image is closer to "good"
            score = 1.0 / (1.0 + math.exp(-k * delta))
            results[dim] = round(score, 2)

        logger.info(
            "TIME logits — deltas: T=%.3f I=%.3f M=%.3f E=%.3f | "
            "scores: T=%.2f I=%.2f M=%.2f E=%.2f",
            deltas[0], deltas[1], deltas[2], deltas[3],
            results["tissue"], results["inflammation"],
            results["moisture"], results["edge"],
        )
        return results
