"""MedASR wrapper — medical speech-to-text for nurse voice notes."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)


class MedASRWrapper:
    """Thin wrapper around the MedASR (Whisper-based) ASR pipeline."""

    def __init__(self, model_name: str, device: str, *, mock: bool = False) -> None:
        self.model_name = model_name
        self.device = device
        self.mock = mock
        self._pipe: Any = None

    def load(self) -> None:
        if self.mock:
            logger.info("MedASR running in MOCK mode.")
            return
        from transformers import pipeline  # type: ignore[import-untyped]

        logger.info("Loading MedASR model %s on %s ...", self.model_name, self.device)
        self._pipe = pipeline(
            "automatic-speech-recognition",
            model=self.model_name,
            device=self.device,
        )
        logger.info("MedASR loaded.")

    def transcribe(self, audio_path: str) -> str:
        """Transcribe an audio file to text."""
        if self.mock:
            return (
                "Patient wound appears to be improving with good granulation tissue. "
                "Slight redness around the edges but no signs of infection. "
                "Dressing changed, moist wound environment maintained."
            )

        result = self._pipe(audio_path, chunk_length_s=20, stride_length_s=2)
        return result["text"]
