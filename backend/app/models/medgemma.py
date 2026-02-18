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

BURN_CLASSIFICATION_PROMPT = """\
Burn care specialist. Classify this burn wound photograph using 4 clinical dimensions.
Score each dimension independently from 0.0 (worst) to 1.0 (best/healed).
Be specific: describe what you see in the image.

T (Tissue/Depth): 0.0=deep full-thickness eschar/charring → 0.3=deep partial-thickness with necrosis → 0.5=superficial partial-thickness with blistering → 0.7=debrided clean wound bed → 0.9=active re-epithelialization → 1.0=healed.
I (Inflammation): 0.0=burn wound sepsis/invasive infection → 0.3=cellulitis/purulent exudate → 0.5=significant periwound erythema → 0.7=mild erythema → 0.9=minimal → 1.0=none.
M (Moisture): 0.0=desiccated eschar or heavily exudative → 0.3=imbalanced → 0.5=moderately excessive → 0.7=nearly balanced → 0.9=optimal → 1.0=perfect.
E (Edge/Re-epithelialization): 0.0=no advancement/graft failure → 0.3=scattered epithelial islands → 0.5=partial re-epithelialization from edges → 0.7=confluent epithelial coverage → 0.9=near-complete closure → 1.0=fully closed.

Respond with JSON only:
{"tissue":{"type":"what you observe","score":0.00},"inflammation":{"type":"what you observe","score":0.00},"moisture":{"type":"what you observe","score":0.00},"edge":{"type":"what you observe","score":0.00}}"""


def _is_burn(wound_type: str | None) -> bool:
    """Check if the wound type is a burn."""
    return wound_type is not None and "burn" in wound_type.lower()


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
    is_burn = _is_burn(wound_type)
    if is_burn:
        parts = [
            "You are a burn care specialist. Analyze the burn wound image and data below.",
            "Consider burn depth (superficial/partial/full-thickness), re-epithelialization status, and graft integration if applicable.",
            "Include burn-specific recommendations: topical agents, grafting needs, hypertrophic scar prevention, and burn center referral criteria.",
            "Respond with a JSON object ONLY. No markdown, no explanation outside the JSON.",
            "",
        ]
    else:
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
    """Remove MedGemma thinking/reasoning blocks and preamble text.

    MedGemma-IT wraps internal reasoning in ``<unused94>thought ... <unused94>``
    delimiters.  We strip the entire block.  If there is no closing token we
    discard everything up to the first JSON-like ``{`` character.

    Also handles plain-text preamble that the model may emit before JSON.
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
        idx = text.find("{")
        if idx != -1:
            text = text[idx:]
        else:
            return ""

    # Remove any remaining stray special tokens
    text = re.sub(r"<unused\d+>", "", text)
    text = re.sub(r"<\|.*?\|>", "", text)

    # Pattern 3: plain-text preamble before JSON (e.g. "Here is the assessment:\n{...")
    # If there's a '{' in the text, check if there's narrative text before it
    brace_idx = text.find("{")
    if brace_idx > 0:
        before = text[:brace_idx].strip()
        # If the preamble is just narrative (no JSON structure), skip it
        if before and "}" not in before:
            text = text[brace_idx:]

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


def _repair_json_string(text: str) -> str:
    """Fix common JSON malformations from LLM output."""
    # Remove trailing commas before } or ]
    text = re.sub(r",\s*([}\]])", r"\1", text)
    # Fix single quotes to double quotes (crude but effective for simple JSON)
    # Only if no double-quoted strings present
    if '"' not in text and "'" in text:
        text = text.replace("'", '"')
    # Remove trailing text after the last }
    last_brace = text.rfind("}")
    if last_brace != -1 and last_brace < len(text) - 1:
        after = text[last_brace + 1:].strip()
        if after and not after.startswith("]"):
            text = text[: last_brace + 1]
    return text


def _extract_json_block(text: str) -> str:
    """Extract JSON from model output that may contain thinking tokens or markdown."""
    text = _strip_thinking(text)

    # Try markdown code block first
    match = re.search(r"```(?:json)?\s*\n?(.*?)\n?\s*```", text, re.DOTALL)
    if match:
        return _repair_json_string(match.group(1).strip())

    # Try balanced-brace extraction (handles nested JSON correctly)
    balanced = _find_balanced_json(text)
    if balanced:
        return _repair_json_string(balanced)

    return _repair_json_string(text.strip())


def _normalize_time_scores(data: dict[str, Any]) -> dict[str, Any] | None:
    """Normalize a parsed JSON dict into canonical TIME format.

    Handles:
    - Case-insensitive keys (Tissue, TISSUE, tissue)
    - Prefix matching (Tissue_quality -> tissue, Inflam... -> inflammation)
    - Values as dicts {"type":..., "score":...} or plain floats/strings
    - Alternate key names (description/observation instead of type)
    - Scores slightly out of [0,1] range (clamped)

    Returns None if a required dimension cannot be resolved.
    """
    dims = ["tissue", "inflammation", "moisture", "edge"]
    result: dict[str, Any] = {}

    for dim in dims:
        val = None
        # Try exact match (case-insensitive)
        for k, v in data.items():
            kl = k.lower().strip()
            if kl == dim:
                val = v
                break
        # Try prefix match (first 4 chars)
        if val is None:
            for k, v in data.items():
                kl = k.lower().strip()
                if kl.startswith(dim[:4]):
                    val = v
                    break
        # Try single-letter match for T/I/M/E keys
        if val is None:
            letter = dim[0].upper()
            for k, v in data.items():
                if k.strip() == letter:
                    val = v
                    break

        if val is None:
            return None

        # Normalize to {"type": str, "score": float}
        if isinstance(val, dict):
            score = val.get("score", val.get("value"))
            desc = val.get("type", val.get("description", val.get("observation", "observed")))
            if score is None:
                # Maybe the dict has only numeric values — take the first float
                for dv in val.values():
                    try:
                        score = float(dv)
                        break
                    except (TypeError, ValueError):
                        continue
            if score is None:
                return None
            try:
                score = float(score)
            except (TypeError, ValueError):
                return None
            result[dim] = {"type": str(desc), "score": score}
        elif isinstance(val, (int, float)):
            result[dim] = {"type": "observed", "score": float(val)}
        elif isinstance(val, str):
            # Try to extract a float from the string
            match = re.search(r"(\d+\.?\d*)", val)
            if match:
                result[dim] = {"type": "observed", "score": float(match.group(1))}
            else:
                return None
        else:
            return None

    # Clamp scores to [0, 1]
    for dim in dims:
        s = result[dim]["score"]
        if 0.0 <= s <= 1.0:
            continue
        if -0.1 <= s <= 1.1:
            result[dim]["score"] = max(0.0, min(1.0, s))
        elif 0 <= s <= 10:
            # Model returned 0-10 scale instead of 0-1
            result[dim]["score"] = round(s / 10.0, 2)
        elif 0 <= s <= 100:
            # Model returned percentage
            result[dim]["score"] = round(s / 100.0, 2)
        else:
            return None

    return result


def _extract_scores_regex(text: str) -> dict[str, Any] | None:
    """Last-resort extraction of TIME scores using regex patterns on raw text.

    Handles outputs like:
    - 'Tissue: 0.7, Inflammation: 0.8, Moisture: 0.5, Edge: 0.6'
    - 'T=0.7 I=0.8 M=0.5 E=0.6'
    """
    dims = {"tissue": None, "inflammation": None, "moisture": None, "edge": None}
    patterns = [
        # "Tissue: 0.7" or "Tissue = 0.7" or "Tissue (0.7)"
        (r"(?i)tissue\b[^0-9]*?(\d+\.?\d*)", "tissue"),
        (r"(?i)inflam\w*\b[^0-9]*?(\d+\.?\d*)", "inflammation"),
        (r"(?i)moisture\b[^0-9]*?(\d+\.?\d*)", "moisture"),
        (r"(?i)edge\b[^0-9]*?(\d+\.?\d*)", "edge"),
    ]
    for pattern, dim in patterns:
        m = re.search(pattern, text)
        if m:
            dims[dim] = float(m.group(1))

    if all(v is not None for v in dims.values()):
        result = {dim: {"type": "observed", "score": v} for dim, v in dims.items()}
        return _normalize_time_scores(result)
    return None


def parse_time_json(text: str) -> dict[str, Any]:
    """Parse TIME classification JSON from model output.

    Uses a multi-strategy approach:
    1. Extract JSON block and parse
    2. Normalize keys/values flexibly (case-insensitive, prefix match, plain floats)
    3. Fallback to regex extraction from raw text

    Raises ValueError only when all strategies fail.
    """
    logger.info("Raw MedGemma output (first 500 chars): %.500s", text)

    raw = _extract_json_block(text)
    logger.debug("Extracted JSON block (first 400 chars): %s", raw[:400])

    # Strategy 1: parse JSON and normalize
    try:
        data = json.loads(raw)
        normalized = _normalize_time_scores(data)
        if normalized is not None:
            return normalized
        logger.warning(
            "JSON parsed but normalization failed — keys present: %s",
            list(data.keys()),
        )
    except json.JSONDecodeError as exc:
        logger.warning(
            "JSON parse failed: %s — extracted block: %.200s",
            exc, raw,
        )

    # Strategy 2: regex extraction from raw text
    regex_result = _extract_scores_regex(text)
    if regex_result is not None:
        logger.info("TIME scores recovered via regex fallback.")
        return regex_result

    raise ValueError(
        f"Could not parse TIME response after all strategies. "
        f"Raw output (first 300 chars): {text[:300]}"
    )


def parse_json_safe(text: str) -> dict[str, Any]:
    """Best-effort JSON extraction from model output."""
    logger.debug("parse_json_safe input (first 300 chars): %.300s", text)
    raw = _extract_json_block(text)
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Try once more with aggressive repair
        try:
            repaired = _repair_json_string(raw)
            return json.loads(repaired)
        except json.JSONDecodeError:
            pass
        logger.warning("parse_json_safe failed on: %.300s", text)
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

# Burn-specific mock labels — same 10-bucket structure
_BURN_TISSUE_LABELS = [
    "deep full-thickness charring",
    "full-thickness eschar",
    "deep partial-thickness with necrosis",
    "deep partial-thickness blistering",
    "superficial partial-thickness with intact blisters",
    "debrided superficial partial wound bed",
    "clean granulating burn wound",
    "early re-epithelialization from edges",
    "confluent re-epithelialization",
    "healed with minimal scarring",
]
_BURN_INFLAMMATION_LABELS = [
    "burn wound sepsis",
    "invasive wound infection",
    "cellulitis with purulent exudate",
    "moderate periwound cellulitis",
    "significant periwound erythema",
    "moderate erythema",
    "mild periwound erythema",
    "minimal inflammatory signs",
    "trace periwound warmth",
    "clean periwound skin",
]
_BURN_MOISTURE_LABELS = [
    "desiccated eschar",
    "very dry burn wound",
    "dry wound bed with cracking",
    "heavily exudative",
    "moderately excessive exudate",
    "slightly imbalanced moisture",
    "nearly balanced",
    "adequately moist wound bed",
    "well-balanced moisture",
    "optimal moisture",
]
_BURN_EDGE_LABELS = [
    "no epithelial advancement",
    "graft failure with exposed bed",
    "scattered epithelial islands",
    "early marginal re-epithelialization",
    "partial confluent re-epithelialization",
    "graft take with partial integration",
    "good graft take",
    "advancing epithelial front",
    "near-complete epithelial closure",
    "complete wound closure",
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


def _mock_time_classification(
    image_path: str | None = None,
    wound_type: str | None = None,
) -> dict[str, Any]:
    """Return deterministic, varied TIME scores based on the image path hash.

    The same image always produces identical scores. Different images produce
    different but clinically plausible scores across the full 0.0-1.0 range.
    Uses burn-specific labels when wound_type contains "burn".
    """
    seed = image_path or str(random.random())

    t_score = _hash_to_score(seed, "tissue")
    i_score = _hash_to_score(seed, "inflammation")
    m_score = _hash_to_score(seed, "moisture")
    e_score = _hash_to_score(seed, "edge")

    if _is_burn(wound_type):
        t_labels, i_labels, m_labels, e_labels = (
            _BURN_TISSUE_LABELS, _BURN_INFLAMMATION_LABELS,
            _BURN_MOISTURE_LABELS, _BURN_EDGE_LABELS,
        )
    else:
        t_labels, i_labels, m_labels, e_labels = (
            _TISSUE_LABELS, _INFLAMMATION_LABELS,
            _MOISTURE_LABELS, _EDGE_LABELS,
        )

    return {
        "tissue": {"type": _label_for_score(t_score, t_labels), "score": t_score},
        "inflammation": {"type": _label_for_score(i_score, i_labels), "score": i_score},
        "moisture": {"type": _label_for_score(m_score, m_labels), "score": m_score},
        "edge": {"type": _label_for_score(e_score, e_labels), "score": e_score},
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
    """Thin wrapper around the MedGemma VLM with optional LoRA adapter."""

    def __init__(
        self, model_name: str, device: str, *, mock: bool = False, lora_path: str = "",
    ) -> None:
        self.model_name = model_name
        self.device = device
        self.mock = mock
        self.lora_path = lora_path
        self._model: Any = None
        self._processor: Any = None
        self._has_lora = False

    def load(self) -> None:
        if self.mock:
            logger.info("MedGemma running in MOCK mode.")
            return
        from transformers import AutoModelForImageTextToText, AutoProcessor

        logger.info("Loading MedGemma model %s on %s ...", self.model_name, self.device)
        self._processor = AutoProcessor.from_pretrained(
            self.model_name, trust_remote_code=True, padding_side="left",
        )
        self._model = AutoModelForImageTextToText.from_pretrained(
            self.model_name,
            torch_dtype=torch.bfloat16,
            device_map="auto" if self.device == "cuda" else None,
            trust_remote_code=True,
        )
        if self.device != "cuda":
            self._model = self._model.to(self.device)

        # Load LoRA adapter if path is set and exists
        if self.lora_path:
            import os
            if os.path.isdir(self.lora_path):
                from peft import PeftModel
                logger.info("Loading LoRA adapter from %s ...", self.lora_path)
                self._model = PeftModel.from_pretrained(self._model, self.lora_path)
                self._has_lora = True
                logger.info("LoRA adapter loaded.")
            else:
                logger.warning("LoRA path %s not found, running base model only.", self.lora_path)

        self._model = self._model.eval()
        logger.info("MedGemma loaded (lora=%s).", self._has_lora)

    def _generate(self, image: Image.Image, prompt: str, max_new_tokens: int = 1024) -> str:
        """Run single-image inference and return generated text."""
        messages = [
            {
                "role": "user",
                "content": [
                    {"type": "image"},
                    {"type": "text", "text": prompt},
                ],
            }
        ]
        input_text = self._processor.apply_chat_template(
            messages, add_generation_prompt=True, tokenize=False,
        )
        inputs = self._processor(
            text=input_text,
            images=[[image]],
            return_tensors="pt",
        ).to(self._model.device)

        with torch.no_grad():
            output_ids = self._model.generate(
                **inputs, max_new_tokens=max_new_tokens, do_sample=False,
            )
        generated = output_ids[0][inputs["input_ids"].shape[1]:]
        return self._processor.decode(generated, skip_special_tokens=True).strip()

    # ---- TIME classification ------------------------------------------------

    def classify_time(
        self, image: Image.Image, *, image_path: str | None = None, wound_type: str | None = None,
    ) -> dict[str, Any]:
        """Classify wound using the TIME framework.

        Tries up to 3 times with progressively stricter prompts.
        Uses burn-specific prompt and labels when wound_type contains "burn".
        """
        if self.mock:
            seed = image_path or getattr(image, "filename", None)
            return _mock_time_classification(image_path=seed, wound_type=wound_type)

        base_prompt = BURN_CLASSIFICATION_PROMPT if _is_burn(wound_type) else TIME_CLASSIFICATION_PROMPT

        # Progressively stricter prompt suffixes
        suffixes = [
            "",
            "\nIMPORTANT: Respond with valid JSON only. No explanation, no markdown.",
            (
                "\nYou MUST respond with ONLY a JSON object, nothing else. "
                'Example: {"tissue":{"type":"granulation","score":0.6},'
                '"inflammation":{"type":"mild erythema","score":0.7},'
                '"moisture":{"type":"balanced","score":0.8},'
                '"edge":{"type":"advancing","score":0.5}}'
            ),
        ]
        max_retries = len(suffixes)
        last_error: Exception | None = None

        for attempt in range(max_retries):
            prompt = base_prompt + suffixes[attempt]
            text = self._generate(image, prompt)
            logger.info(
                "classify_time attempt %d/%d — raw output (first 500 chars): %.500s",
                attempt + 1, max_retries, text,
            )
            try:
                return parse_time_json(text)
            except ValueError as exc:
                last_error = exc
                logger.warning(
                    "classify_time parse failed (attempt %d/%d): %s",
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
        raw_text = self._generate(image, prompt, max_new_tokens=1500)
        logger.info("Report raw output (first 500 chars): %.500s", raw_text)

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

        # Fallback: if model returned something useful but not in our JSON format,
        # wrap it in a basic report structure
        logger.warning("Report JSON parse failed, constructing fallback report.")
        clean_text = _strip_thinking(raw_text)
        if not clean_text or len(clean_text) < 20:
            # Model returned garbage — use the mock report as fallback
            return _mock_report(
                time_scores, trajectory,
                patient_name=patient_name,
                wound_type=wound_type,
                wound_location=wound_location,
                visit_date=visit_date,
            )
        # Return the cleaned model text wrapped in a report header
        avg = sum(d["score"] for d in time_scores.values()) / 4
        return (
            f"## Wound Assessment Report\n\n"
            f"**Patient:** {patient_name or 'Not recorded'}\n"
            f"**Wound type:** {wound_type or 'Not specified'}\n"
            f"**Trajectory:** {trajectory}\n"
            f"**Composite score:** {max(1, min(10, round(avg * 10)))}/10\n\n"
            f"### AI Analysis\n\n{clean_text}\n"
        )

    # ---- Contradiction detection --------------------------------------------

    def detect_contradiction(
        self, trajectory: str, nurse_notes: str, image: Image.Image | None = None,
    ) -> dict[str, Any]:
        """Detect contradiction between AI trajectory and nurse notes.

        If *image* is provided, it is passed to the model for context.
        Otherwise a small white placeholder is used (MedGemma requires an image).
        """
        if self.mock:
            return {"contradiction": False, "detail": None}

        prompt = (
            f"The AI wound assessment determined the trajectory is '{trajectory}'. "
            f"The nurse recorded the following notes: '{nurse_notes}'. "
            "Is there a meaningful contradiction between the AI assessment and nurse notes? "
            'Respond with JSON only: {"contradiction": true, "detail": "explanation"} '
            'or {"contradiction": false, "detail": null}'
        )
        # MedGemma VLM requires an image — use the wound image if available,
        # otherwise create a neutral placeholder (white, not black, to avoid
        # confusing the model with a dark/blank input).
        ctx_image = image if image is not None else Image.new("RGB", (64, 64), (255, 255, 255))
        try:
            text = self._generate(ctx_image, prompt, max_new_tokens=200)
            result = parse_json_safe(text)
        except Exception as exc:
            logger.warning("Contradiction detection failed: %s", exc)
            return {"contradiction": False, "detail": None}

        # Robust extraction: "contradiction" can be bool or string "true"/"false"
        raw_flag = result.get("contradiction", False)
        if isinstance(raw_flag, str):
            raw_flag = raw_flag.lower().strip() in ("true", "yes", "1")

        return {
            "contradiction": bool(raw_flag),
            "detail": result.get("detail"),
        }
