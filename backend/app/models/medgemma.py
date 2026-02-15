"""MedGemma wrapper — TIME classification, report generation, contradiction detection."""

from __future__ import annotations

import hashlib
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
You are a wound care specialist performing a detailed TIME framework assessment.

First, think step by step about what you observe in the wound image. Consider:
- The color and texture of the wound bed (black, yellow, red, pink)
- Presence of slough, necrotic tissue, or granulation tissue
- Surrounding skin condition (erythema, maceration, induration, callus)
- Signs of exudate (amount, color, viscosity)
- Wound edge characteristics (rolled, undermined, attached, epithelializing)

Then score each TIME dimension from 0.0 to 1.0 using the FULL decimal range. \
Use the full range from 0.0 to 1.0 with decimal precision (e.g. 0.15, 0.33, 0.62, 0.85), \
not just round numbers like 0.0, 0.5, or 1.0. Each wound is unique and scores should \
reflect that specificity.

TIME dimensions with scoring guidance:
- T (Tissue): Wound bed tissue quality.
  0.0 = necrotic/eschar (black, hard, adherent)
  0.1 = mostly necrotic with minimal viable tissue
  0.2 = thick slough covering most of wound bed
  0.3 = moderate slough (yellow/grey fibrin, >50% coverage)
  0.4 = slough mixed with early granulation
  0.5 = patchy granulation, some slough remaining
  0.6 = predominantly granulating with residual fibrin
  0.7 = healthy granulation (beefy red, cobblestone texture)
  0.8 = robust granulation with early epithelial islands
  0.9 = mostly epithelialized with small granulating areas
  1.0 = fully epithelialized (pink, smooth, intact skin)

- I (Inflammation/Infection): Degree of inflammation or infection.
  0.0 = systemic infection signs (purulent exudate, foul odor, cellulitis spreading)
  0.1 = severe local infection (abscess, heavy purulence)
  0.2 = moderate infection (green/brown exudate, increasing pain)
  0.3 = critical colonization (delayed healing, friable granulation)
  0.4 = significant erythema extending >2cm from wound edge
  0.5 = moderate periwound erythema (1-2cm), warmth present
  0.6 = mild erythema limited to wound margin
  0.7 = minimal inflammation, slight warmth
  0.8 = trace erythema only, no warmth
  0.9 = periwound skin nearly normal, very slight discoloration
  1.0 = no inflammation, healthy periwound skin

- M (Moisture): Wound moisture balance.
  0.0 = completely desiccated (dry, cracked wound bed)
  0.1 = very dry with adherent dressing on removal
  0.2 = dry wound bed, minimal moisture
  0.3 = excessive moisture (macerated periwound, saturated dressings)
  0.4 = moderately excessive (periwound showing early maceration)
  0.5 = slightly too moist or slightly too dry
  0.6 = nearly balanced with minor excess
  0.7 = adequately moist, thin serous exudate
  0.8 = well-balanced moisture, healthy wound bed glistening
  0.9 = optimal moisture environment
  1.0 = perfectly balanced (moist wound bed, intact periwound)

- E (Edge): Wound edge and periwound skin condition.
  0.0 = undermined/tunneling with tissue destruction
  0.1 = significant undermining, detached edges
  0.2 = rolled/epibole edges preventing migration
  0.3 = thickened, non-advancing edges with callus
  0.4 = edges attached but no visible contraction
  0.5 = minimally advancing, early contraction signs
  0.6 = edges attached with slow but visible contraction
  0.7 = good edge attachment, moderate contraction
  0.8 = actively contracting with early epithelial migration
  0.9 = strong epithelial advancement from edges
  1.0 = fully advancing/closed (complete epithelial coverage)

Return ONLY valid JSON in this exact format, nothing else:
{
  "tissue": {"type": "<descriptive label>", "score": <float>},
  "inflammation": {"type": "<descriptive label>", "score": <float>},
  "moisture": {"type": "<descriptive label>", "score": <float>},
  "edge": {"type": "<descriptive label>", "score": <float>}
}
"""


def _build_report_prompt(
    time_scores: dict[str, Any],
    trajectory: str,
    change_score: float | None,
    nurse_notes: str | None,
    contradiction: dict[str, Any],
    *,
    patient_name: str | None = None,
    wound_type: str | None = None,
    wound_location: str | None = None,
    visit_date: str | None = None,
) -> str:
    parts = [
        "You are a wound care specialist. Generate a structured clinical wound assessment report.",
        "Use the patient and wound details provided below. Do NOT use placeholders such as "
        '"[Patient Name]", "[Date]", or "[Specify location]" — all relevant data is supplied.',
        "",
    ]

    # Patient context section
    parts.append("## Patient Information")
    parts.append(f"- Patient: {patient_name or 'Not recorded'}")
    parts.append(f"- Wound type: {wound_type or 'Not specified'}")
    parts.append(f"- Wound location: {wound_location or 'Not specified'}")
    parts.append(f"- Visit date: {visit_date or 'Not recorded'}")
    parts.append("")

    parts.extend([
        "## TIME Classification",
        f"- Tissue: {time_scores['tissue']['type']} (score {time_scores['tissue']['score']:.2f})",
        f"- Inflammation: {time_scores['inflammation']['type']} (score {time_scores['inflammation']['score']:.2f})",
        f"- Moisture: {time_scores['moisture']['type']} (score {time_scores['moisture']['score']:.2f})",
        f"- Edge: {time_scores['edge']['type']} (score {time_scores['edge']['score']:.2f})",
        "",
        f"## Trajectory: {trajectory}",
    ])
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
        raw_score = float(entry.get("score", 0.0))
        result[key] = {
            "type": str(entry.get("type", "unknown")),
            "score": max(0.0, min(1.0, raw_score)),
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

# Tissue type labels keyed by score buckets (index 0-9 maps to 0.0-0.9 range start).
_TISSUE_LABELS = [
    "necrotic eschar",
    "mostly necrotic",
    "thick slough",
    "moderate slough",
    "slough with early granulation",
    "patchy granulation",
    "predominantly granulating",
    "healthy granulation",
    "robust granulation with epithelial islands",
    "mostly epithelialized",
]
_INFLAMMATION_LABELS = [
    "severe infection with cellulitis",
    "severe local infection",
    "moderate infection",
    "critical colonization",
    "significant periwound erythema",
    "moderate erythema",
    "mild periwound erythema",
    "minimal inflammation",
    "trace erythema",
    "near-normal periwound skin",
]
_MOISTURE_LABELS = [
    "desiccated",
    "very dry",
    "dry wound bed",
    "excessive moisture with maceration",
    "moderately excessive moisture",
    "slightly imbalanced",
    "nearly balanced",
    "adequately moist",
    "well-balanced moisture",
    "optimal moisture",
]
_EDGE_LABELS = [
    "undermined with tunneling",
    "significant undermining",
    "rolled epibole edges",
    "thickened non-advancing edges",
    "attached but non-advancing",
    "minimally advancing",
    "slow contraction",
    "moderate contraction",
    "actively contracting",
    "strong epithelial advancement",
]


def _hash_to_score(seed: str, dimension: str, low: float = 0.1, high: float = 0.95) -> float:
    """Derive a deterministic score from a seed string and dimension name.

    Returns a float in [low, high] rounded to 2 decimals. The same seed+dimension
    always produces the same score, but different dimensions produce different values.
    """
    h = hashlib.sha256(f"{seed}:{dimension}".encode()).hexdigest()
    # Use first 8 hex chars as a fraction in [0, 1)
    fraction = int(h[:8], 16) / 0xFFFFFFFF
    score = low + fraction * (high - low)
    return round(score, 2)


def _label_for_score(score: float, labels: list[str]) -> str:
    """Pick a label from a 10-element list based on a 0.0-1.0 score."""
    idx = min(int(score * 10), len(labels) - 1)
    return labels[idx]


def _mock_time_classification(image_path: str | None = None) -> dict[str, Any]:
    """Return deterministic, varied TIME scores based on the image path hash.

    The same image always produces identical scores. Different images produce
    different but clinically plausible scores across the full 0.0-1.0 range.
    """
    seed = image_path or str(random.random())

    t_score = _hash_to_score(seed, "tissue")
    i_score = _hash_to_score(seed, "inflammation")
    m_score = _hash_to_score(seed, "moisture")
    e_score = _hash_to_score(seed, "edge")

    return {
        "tissue": {"type": _label_for_score(t_score, _TISSUE_LABELS), "score": t_score},
        "inflammation": {"type": _label_for_score(i_score, _INFLAMMATION_LABELS), "score": i_score},
        "moisture": {"type": _label_for_score(m_score, _MOISTURE_LABELS), "score": m_score},
        "edge": {"type": _label_for_score(e_score, _EDGE_LABELS), "score": e_score},
    }


def _mock_report(
    time_scores: dict[str, Any],
    trajectory: str,
    *,
    patient_name: str | None = None,
    wound_type: str | None = None,
    wound_location: str | None = None,
    visit_date: str | None = None,
) -> str:
    avg = sum(d["score"] for d in time_scores.values()) / 4

    # Determine clinical recommendation based on composite score
    if avg >= 0.7:
        status = "The wound is healing well with favorable indicators across all TIME dimensions."
        recommendation = (
            "- Continue current wound care protocol.\n"
            "- Maintain moisture balance with current dressing regimen.\n"
            "- Schedule routine follow-up in 7-10 days."
        )
    elif avg >= 0.4:
        status = "The wound shows moderate healing progress with some areas requiring attention."
        recommendation = (
            "- Review and consider adjusting the current dressing type.\n"
            "- Monitor periwound skin for signs of maceration or breakdown.\n"
            "- Consider nutritional assessment to support healing.\n"
            "- Schedule follow-up in 5-7 days."
        )
    else:
        status = "The wound presents concerning indicators that require prompt clinical intervention."
        recommendation = (
            "- Obtain wound culture if infection is suspected.\n"
            "- Consider debridement of non-viable tissue.\n"
            "- Reassess offloading and pressure redistribution.\n"
            "- Escalate to wound care specialist if not already involved.\n"
            "- Schedule follow-up within 2-3 days."
        )

    return (
        f"## Wound Assessment Report (MOCK)\n\n"
        f"**Patient:** {patient_name or 'Not recorded'}\n"
        f"**Wound type:** {wound_type or 'Not specified'}\n"
        f"**Location:** {wound_location or 'Not specified'}\n"
        f"**Visit date:** {visit_date or 'Not recorded'}\n"
        f"**Trajectory:** {trajectory}\n\n"
        f"### Clinical Summary\n"
        f"{status}\n\n"
        f"### TIME Assessment\n"
        f"- Tissue: {time_scores['tissue']['type']} ({time_scores['tissue']['score']:.2f})\n"
        f"- Inflammation: {time_scores['inflammation']['type']} ({time_scores['inflammation']['score']:.2f})\n"
        f"- Moisture: {time_scores['moisture']['type']} ({time_scores['moisture']['score']:.2f})\n"
        f"- Edge: {time_scores['edge']['type']} ({time_scores['edge']['score']:.2f})\n\n"
        f"**Composite score:** {avg:.2f}\n\n"
        f"### Recommendations\n"
        f"{recommendation}\n"
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

    def classify_time(self, image: Image.Image, *, image_path: str | None = None) -> dict[str, Any]:
        """Classify wound using the TIME framework. Retries once on JSON parse failure."""
        if self.mock:
            # Use provided path, fall back to PIL filename, then random seed
            seed = image_path or getattr(image, "filename", None)
            return _mock_time_classification(image_path=seed)

        max_retries = 2
        last_error: Exception | None = None
        for attempt in range(max_retries):
            prompt = TIME_CLASSIFICATION_PROMPT
            if attempt > 0:
                prompt += "\nRemember: respond with valid JSON only."
            messages = [
                {
                    "role": "user",
                    "content": [
                        {"type": "image", "image": image},
                        {"type": "text", "text": prompt},
                    ],
                }
            ]
            output = self._pipe(text=messages, max_new_tokens=500)
            text: str = output[0]["generated_text"][-1]["content"]
            try:
                return parse_time_json(text)
            except ValueError as exc:
                last_error = exc
                logger.warning(
                    "classify_time JSON parse failed (attempt %d/%d): %s",
                    attempt + 1, max_retries, exc,
                )
        raise last_error  # type: ignore[misc]

    # ---- Report generation --------------------------------------------------

    def generate_report(
        self,
        image: Image.Image,
        time_scores: dict[str, Any],
        trajectory: str,
        change_score: float | None,
        nurse_notes: str | None,
        contradiction: dict[str, Any],
        *,
        patient_name: str | None = None,
        wound_type: str | None = None,
        wound_location: str | None = None,
        visit_date: str | None = None,
    ) -> str:
        """Generate a structured wound assessment report."""
        if self.mock:
            return _mock_report(
                time_scores, trajectory,
                patient_name=patient_name,
                wound_type=wound_type,
                wound_location=wound_location,
                visit_date=visit_date,
            )

        prompt = _build_report_prompt(
            time_scores, trajectory, change_score, nurse_notes, contradiction,
            patient_name=patient_name,
            wound_type=wound_type,
            wound_location=wound_location,
            visit_date=visit_date,
        )
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
