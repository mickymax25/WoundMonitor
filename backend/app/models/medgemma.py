"""MedGemma wrapper — TIME classification, report generation, contradiction detection."""

from __future__ import annotations

import json
import logging
import random
import re
from typing import Any

from PIL import Image

try:
    import torch
except ImportError:
    torch = None  # type: ignore[assignment]

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Prompt templates
# ---------------------------------------------------------------------------

TIME_CLASSIFICATION_PROMPT = """\
You are a wound care specialist. Analyze the wound image using the TIME framework \
and provide structured scores.

For each TIME dimension, provide:
- type: a short descriptive label
- score: a number from 0.0 (worst) to 1.0 (best/healthy)

TIME dimensions:
- T (Tissue): Evaluate the wound bed tissue type (necrotic=0, slough=0.3, granulation=0.7, epithelial=1.0)
- I (Inflammation/Infection): Evaluate inflammation and signs of infection (severe infection=0, moderate=0.4, mild=0.7, none=1.0)
- M (Moisture): Evaluate wound moisture balance (desiccated=0, excessive=0.3, balanced=1.0)
- E (Edge): Evaluate wound edge advancement (undermined=0, rolled=0.3, attached=0.7, advancing=1.0)

Return ONLY valid JSON in this exact format, nothing else:
{
  "tissue": {"type": "<label>", "score": <float>},
  "inflammation": {"type": "<label>", "score": <float>},
  "moisture": {"type": "<label>", "score": <float>},
  "edge": {"type": "<label>", "score": <float>}
}
"""


def _build_report_prompt(
    time_scores: dict[str, Any],
    trajectory: str,
    change_score: float | None,
    nurse_notes: str | None,
    contradiction: dict[str, Any],
) -> str:
    parts = [
        "You are a wound care specialist. Generate a structured clinical wound assessment report.",
        "",
        "## TIME Classification",
        f"- Tissue: {time_scores['tissue']['type']} (score {time_scores['tissue']['score']:.2f})",
        f"- Inflammation: {time_scores['inflammation']['type']} (score {time_scores['inflammation']['score']:.2f})",
        f"- Moisture: {time_scores['moisture']['type']} (score {time_scores['moisture']['score']:.2f})",
        f"- Edge: {time_scores['edge']['type']} (score {time_scores['edge']['score']:.2f})",
        "",
        f"## Trajectory: {trajectory}",
    ]
    if change_score is not None:
        parts.append(f"Cosine change score: {change_score:.4f}")
    if nurse_notes:
        parts.append(f"\n## Nurse Notes\n{nurse_notes}")
    if contradiction.get("contradiction"):
        parts.append(f"\n## Contradiction detected\n{contradiction.get('detail', 'N/A')}")
    parts.append(
        "\nProvide a concise clinical summary with: "
        "1) Current wound status, 2) Change since last visit, "
        "3) Recommended interventions, 4) Follow-up timeline."
    )
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# JSON parsing helpers
# ---------------------------------------------------------------------------

def _extract_json_block(text: str) -> str:
    """Extract JSON from model output that may contain markdown fences or extra text."""
    # Try markdown code block first
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if match:
        return match.group(1).strip()
    # Try to find raw JSON object
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        return match.group(0).strip()
    return text.strip()


def parse_time_json(text: str) -> dict[str, Any]:
    """Parse TIME classification JSON from model output. Raises ValueError on failure."""
    raw = _extract_json_block(text)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning("Failed to parse TIME JSON: %s — raw text: %s", exc, text[:300])
        raise ValueError(f"Could not parse TIME response: {exc}") from exc

    required_keys = {"tissue", "inflammation", "moisture", "edge"}
    missing = required_keys - set(data.keys())
    if missing:
        raise ValueError(f"TIME response missing keys: {missing}")

    result: dict[str, Any] = {}
    for key in required_keys:
        entry = data[key]
        result[key] = {
            "type": str(entry.get("type", "unknown")),
            "score": float(entry.get("score", 0.0)),
        }
    return result


def parse_json_safe(text: str) -> dict[str, Any]:
    """Best-effort JSON extraction from model output."""
    raw = _extract_json_block(text)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        logger.warning("parse_json_safe failed on: %s", text[:300])
        return {}


# ---------------------------------------------------------------------------
# Mock helpers
# ---------------------------------------------------------------------------

def _mock_time_classification() -> dict[str, Any]:
    return {
        "tissue": {"type": "granulation", "score": round(random.uniform(0.5, 0.9), 2)},
        "inflammation": {"type": "mild erythema", "score": round(random.uniform(0.5, 0.8), 2)},
        "moisture": {"type": "balanced", "score": round(random.uniform(0.6, 1.0), 2)},
        "edge": {"type": "attached, non-advancing", "score": round(random.uniform(0.4, 0.8), 2)},
    }


def _mock_report(time_scores: dict[str, Any], trajectory: str) -> str:
    avg = sum(d["score"] for d in time_scores.values()) / 4
    return (
        f"## Wound Assessment Report (MOCK)\n\n"
        f"**Trajectory:** {trajectory}\n\n"
        f"### TIME Summary\n"
        f"- Tissue: {time_scores['tissue']['type']} ({time_scores['tissue']['score']:.2f})\n"
        f"- Inflammation: {time_scores['inflammation']['type']} ({time_scores['inflammation']['score']:.2f})\n"
        f"- Moisture: {time_scores['moisture']['type']} ({time_scores['moisture']['score']:.2f})\n"
        f"- Edge: {time_scores['edge']['type']} ({time_scores['edge']['score']:.2f})\n\n"
        f"**Composite score:** {avg:.2f}\n\n"
        f"### Recommendations\n"
        f"- Continue current wound care protocol.\n"
        f"- Monitor for signs of infection.\n"
        f"- Schedule follow-up in 5-7 days.\n"
    )


# ---------------------------------------------------------------------------
# Wrapper
# ---------------------------------------------------------------------------

class MedGemmaWrapper:
    """Thin wrapper around the MedGemma VLM pipeline."""

    def __init__(self, model_name: str, device: str, *, mock: bool = False) -> None:
        self.model_name = model_name
        self.device = device
        self.mock = mock
        self._pipe: Any = None

    def load(self) -> None:
        if self.mock:
            logger.info("MedGemma running in MOCK mode.")
            return
        from transformers import pipeline  # type: ignore[import-untyped]

        logger.info("Loading MedGemma model %s on %s ...", self.model_name, self.device)
        self._pipe = pipeline(
            "image-text-to-text",
            model=self.model_name,
            torch_dtype=torch.bfloat16,
            device=self.device,
        )
        logger.info("MedGemma loaded.")

    # ---- TIME classification ------------------------------------------------

    def classify_time(self, image: Image.Image) -> dict[str, Any]:
        """Classify wound using the TIME framework."""
        if self.mock:
            return _mock_time_classification()

        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": image},
                    {"type": "text", "text": TIME_CLASSIFICATION_PROMPT},
                ],
            }
        ]
        output = self._pipe(text=messages, max_new_tokens=500)
        text: str = output[0]["generated_text"][-1]["content"]
        return parse_time_json(text)

    # ---- Report generation --------------------------------------------------

    def generate_report(
        self,
        image: Image.Image,
        time_scores: dict[str, Any],
        trajectory: str,
        change_score: float | None,
        nurse_notes: str | None,
        contradiction: dict[str, Any],
    ) -> str:
        """Generate a structured wound assessment report."""
        if self.mock:
            return _mock_report(time_scores, trajectory)

        prompt = _build_report_prompt(time_scores, trajectory, change_score, nurse_notes, contradiction)
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": image},
                    {"type": "text", "text": prompt},
                ],
            }
        ]
        output = self._pipe(text=messages, max_new_tokens=1500)
        return output[0]["generated_text"][-1]["content"]

    # ---- Contradiction detection --------------------------------------------

    def detect_contradiction(self, trajectory: str, nurse_notes: str) -> dict[str, Any]:
        """Detect contradiction between AI trajectory and nurse notes."""
        if self.mock:
            return {"contradiction": False, "detail": None}

        prompt = (
            f"The AI wound assessment determined the trajectory is '{trajectory}'. "
            f"The nurse recorded the following notes: '{nurse_notes}'. "
            "Determine if there is a meaningful contradiction between the AI assessment and nurse notes. "
            'Return ONLY valid JSON: {"contradiction": true/false, "detail": "explanation or null"}'
        )
        messages = [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
        output = self._pipe(text=messages, max_new_tokens=200)
        text: str = output[0]["generated_text"][-1]["content"]
        result = parse_json_safe(text)
        return {
            "contradiction": bool(result.get("contradiction", False)),
            "detail": result.get("detail"),
        }
