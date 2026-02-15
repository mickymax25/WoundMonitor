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
Wound care specialist. Classify this wound photograph using the TIME framework.
Score each dimension independently from 0.0 (worst) to 1.0 (best).
Be specific: each wound has different characteristics per dimension. Describe what you see.

T (Tissue): 0.0=necrotic eschar → 0.3=fibrin slough → 0.6=granulation → 0.9=epithelializing → 1.0=healed.
I (Inflammation): 0.0=severe infection/cellulitis → 0.3=purulent exudate → 0.6=mild erythema → 0.9=minimal → 1.0=none.
M (Moisture): 0.0=desiccated or macerated → 0.3=imbalanced → 0.6=nearly balanced → 0.9=optimal → 1.0=perfect.
E (Edge): 0.0=undermined/tunneling → 0.3=rolled edges → 0.6=attached/contracting → 0.9=advancing → 1.0=closed.

Respond with JSON only:
{"tissue":{"type":"what you observe","score":0.00},"inflammation":{"type":"what you observe","score":0.00},"moisture":{"type":"what you observe","score":0.00},"edge":{"type":"what you observe","score":0.00}}"""


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
        "You are a wound care specialist. Analyze the wound image and data below.",
        "Respond with a JSON object ONLY. No markdown, no explanation outside the JSON.",
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
        '\nRespond with this exact JSON structure:\n'
        '{"summary": "2-3 sentence clinical summary of wound status",'
        ' "wound_status": "current wound status description",'
        ' "change_analysis": "change since last visit or baseline note",'
        ' "interventions": ["intervention 1", "intervention 2", ...],'
        ' "follow_up": "follow-up timeline recommendation"}'
    )
    return "\n".join(parts)


def _report_json_to_markdown(
    report_data: dict[str, Any],
    time_scores: dict[str, Any],
    trajectory: str,
    *,
    patient_name: str | None = None,
    wound_type: str | None = None,
    wound_location: str | None = None,
    visit_date: str | None = None,
) -> str:
    """Convert structured report JSON to standardized markdown."""
    avg = sum(d["score"] for d in time_scores.values()) / 4

    lines = [
        "## Wound Assessment Report",
        "",
        f"**Patient:** {patient_name or 'Not recorded'}",
        f"**Wound type:** {wound_type or 'Not specified'}",
        f"**Location:** {wound_location or 'Not specified'}",
        f"**Visit date:** {visit_date or 'Not recorded'}",
        f"**Trajectory:** {trajectory}",
        "",
        "### Clinical Summary",
        report_data.get("summary", "No summary available."),
        "",
        "### Current Wound Status",
        report_data.get("wound_status", "No status available."),
        "",
        "### TIME Assessment",
        f"- **Tissue:** {time_scores['tissue']['type']} (healing {max(1, min(10, round(time_scores['tissue']['score'] * 10)))}/10)",
        f"- **Inflammation:** {time_scores['inflammation']['type']} (healing {max(1, min(10, round(time_scores['inflammation']['score'] * 10)))}/10)",
        f"- **Moisture:** {time_scores['moisture']['type']} (healing {max(1, min(10, round(time_scores['moisture']['score'] * 10)))}/10)",
        f"- **Edge:** {time_scores['edge']['type']} (healing {max(1, min(10, round(time_scores['edge']['score'] * 10)))}/10)",
        f"",
        f"**Composite score:** {max(1, min(10, round(avg * 10)))}/10",
        "",
        "### Change Analysis",
        report_data.get("change_analysis", "Baseline assessment — no prior data."),
        "",
        "### Recommended Interventions",
    ]
    interventions = report_data.get("interventions", [])
    if isinstance(interventions, list) and interventions:
        for item in interventions:
            lines.append(f"- {item}")
    else:
        lines.append("- Continue current care protocol.")
    lines.extend([
        "",
        "### Follow-up",
        report_data.get("follow_up", "Schedule follow-up as clinically indicated."),
        "",
    ])
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# JSON parsing helpers
# ---------------------------------------------------------------------------

def _strip_thinking(text: str) -> str:
    """Remove MedGemma thinking/reasoning blocks.

    MedGemma-IT wraps internal reasoning in ``<unused94>thought ... <unused94>``
    delimiters.  We strip the entire block.  If there is no closing token we
    discard everything up to the first JSON-like ``{`` character.
    """
    # Pattern 1: full thinking block  <unusedN>thought ... <unusedN>
    stripped = re.sub(
        r"<unused\d+>\s*thought\b.*?<unused\d+>",
        "",
        text,
        count=1,
        flags=re.DOTALL,
    )
    if stripped != text:
        text = stripped

    # Pattern 2: thinking start with no closing token (truncated output)
    if re.match(r"<unused\d+>\s*thought\b", text):
        # Try to jump straight to the first '{' – the JSON payload
        idx = text.find("{")
        if idx != -1:
            text = text[idx:]
        else:
            # No JSON at all — return empty so caller raises cleanly
            return ""

    # Remove any remaining stray special tokens
    text = re.sub(r"<unused\d+>", "", text)
    text = re.sub(r"<\|.*?\|>", "", text)
    return text.strip()


def _find_balanced_json(text: str) -> str | None:
    """Find the first balanced ``{...}`` block in *text*.

    Respects JSON string escaping so that braces inside strings are not
    counted.  Returns ``None`` when no balanced object is found.
    """
    start = text.find("{")
    if start == -1:
        return None
    depth = 0
    in_string = False
    escape_next = False
    for i in range(start, len(text)):
        ch = text[i]
        if escape_next:
            escape_next = False
            continue
        if ch == "\\" and in_string:
            escape_next = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return None


def _extract_json_block(text: str) -> str:
    """Extract JSON from model output that may contain thinking tokens or markdown."""
    text = _strip_thinking(text)

    # Try markdown code block first
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if match:
        return match.group(1).strip()

    # Try balanced-brace extraction (handles nested JSON correctly)
    balanced = _find_balanced_json(text)
    if balanced:
        return balanced

    return text.strip()


def parse_time_json(text: str) -> dict[str, Any]:
    """Parse TIME classification JSON from model output. Raises ValueError on failure."""
    raw = _extract_json_block(text)
    logger.debug("Extracted JSON block (first 400 chars): %s", raw[:400])
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        logger.warning(
            "Failed to parse TIME JSON: %s — extracted block: %.200s — raw text: %.300s",
            exc, raw, text,
        )
        raise ValueError(f"Could not parse TIME response: {exc}") from exc

    required_keys = {"tissue", "inflammation", "moisture", "edge"}
    missing = required_keys - set(data.keys())
    if missing:
        raise ValueError(f"TIME response missing keys: {missing}")

    result: dict[str, Any] = {}
    for key in required_keys:
        entry = data[key]
        if "score" not in entry:
            raise ValueError(f"Missing 'score' field for {key}: {entry}")
        try:
            raw_score = float(entry["score"])
        except (ValueError, TypeError) as exc:
            raise ValueError(f"Invalid score for {key}: {entry['score']}") from exc
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

    if avg >= 0.7:
        report_data = {
            "summary": "The wound is healing well with favorable indicators across all TIME dimensions.",
            "wound_status": (
                f"Tissue bed shows {time_scores['tissue']['type']} with minimal inflammatory signs. "
                f"Moisture balance is adequate and wound edges are {time_scores['edge']['type']}."
            ),
            "change_analysis": "Positive trajectory noted." if trajectory == "improving" else "Baseline assessment.",
            "interventions": [
                "Continue current wound care protocol.",
                "Maintain moisture balance with current dressing regimen.",
                "Monitor for signs of infection at each dressing change.",
            ],
            "follow_up": "Schedule routine follow-up in 7-10 days.",
        }
    elif avg >= 0.4:
        report_data = {
            "summary": "The wound shows moderate healing progress with some areas requiring attention.",
            "wound_status": (
                f"Tissue presents as {time_scores['tissue']['type']}. "
                f"Inflammation shows {time_scores['inflammation']['type']}. "
                f"Edge status: {time_scores['edge']['type']}."
            ),
            "change_analysis": (
                "Deterioration noted since last visit." if trajectory == "deteriorating"
                else "Stable with gradual progress." if trajectory == "stable"
                else "Baseline assessment."
            ),
            "interventions": [
                "Review and consider adjusting the current dressing type.",
                "Monitor periwound skin for signs of maceration or breakdown.",
                "Consider nutritional assessment to support healing.",
                "Assess need for offloading or pressure redistribution.",
            ],
            "follow_up": "Schedule follow-up in 5-7 days.",
        }
    else:
        report_data = {
            "summary": "The wound presents concerning indicators that require prompt clinical intervention.",
            "wound_status": (
                f"Tissue shows {time_scores['tissue']['type']} with "
                f"{time_scores['inflammation']['type']}. "
                f"Moisture: {time_scores['moisture']['type']}. Edge: {time_scores['edge']['type']}."
            ),
            "change_analysis": (
                "Significant deterioration since last visit — urgent review needed."
                if trajectory == "deteriorating"
                else "Initial assessment reveals poor wound status."
            ),
            "interventions": [
                "Obtain wound culture if infection is suspected.",
                "Consider debridement of non-viable tissue.",
                "Reassess offloading and pressure redistribution.",
                "Escalate to wound care specialist if not already involved.",
                "Review systemic factors affecting healing.",
            ],
            "follow_up": "Schedule follow-up within 2-3 days.",
        }

    return _report_json_to_markdown(
        report_data, time_scores, trajectory,
        patient_name=patient_name,
        wound_type=wound_type,
        wound_location=wound_location,
        visit_date=visit_date,
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
            output = self._pipe(text=messages, max_new_tokens=1024)
            text: str = output[0]["generated_text"][-1]["content"]
            logger.debug("MedGemma raw output (first 500 chars): %s", text[:500])
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
        raw_text: str = output[0]["generated_text"][-1]["content"]

        # Try to parse as JSON and convert to standardized markdown
        report_data = parse_json_safe(raw_text)
        if report_data and "summary" in report_data:
            return _report_json_to_markdown(
                report_data, time_scores, trajectory,
                patient_name=patient_name,
                wound_type=wound_type,
                wound_location=wound_location,
                visit_date=visit_date,
            )
        # Fallback: return raw text if JSON parsing fails
        logger.warning("Report JSON parse failed, returning raw text.")
        return raw_text

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
