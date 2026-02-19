"""WoundAgent — orchestrates the 8-step analysis pipeline.

Steps:
1. MedSigLIP embedding + zero-shot classification
2. MedGemma TIME classification
3. Retrieve previous assessment
4. Compute change score and trajectory
5. Audio transcription (optional)
6. Contradiction detection (optional)
7. Report generation
8. Alert determination
"""

from __future__ import annotations

import json
import logging
from typing import Any

import numpy as np
from PIL import Image
from scipy.spatial.distance import cosine as cosine_distance

from app.models.medgemma import MedGemmaWrapper
from app.models.medsiglip import MedSigLIPWrapper, WOUND_LABELS, BURN_LABELS
from app.models.medasr import MedASRWrapper

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Zero-shot -> TIME fallback (when MedGemma parsing fails)
# ---------------------------------------------------------------------------

# Each MedSigLIP wound label maps to approximate TIME scores [T, I, M, E]
# 0 = worst, 1 = best
_ZEROSHOT_TIME_MAP: dict[str, tuple[float, float, float, float]] = {
    "healthy granulating wound":              (0.70, 0.70, 0.60, 0.60),
    "infected wound with purulent discharge": (0.20, 0.15, 0.30, 0.20),
    "necrotic wound tissue":                  (0.10, 0.40, 0.30, 0.25),
    "wound with fibrin slough":               (0.30, 0.50, 0.50, 0.40),
    "epithelializing wound edge":             (0.60, 0.70, 0.60, 0.75),
    "dry wound bed":                          (0.40, 0.60, 0.20, 0.40),
    "wound with excessive exudate":           (0.35, 0.35, 0.20, 0.35),
    "wound with undermined edges":            (0.30, 0.40, 0.45, 0.15),
}


def zeroshot_to_time_fallback(zeroshot_scores: dict[str, float]) -> dict[str, Any]:
    """Derive approximate TIME scores from MedSigLIP zero-shot classification.

    Used as fallback when MedGemma fails to produce valid TIME JSON.
    Returns scores in canonical format: {dim: {"type": str, "score": float}}.
    """
    t_sum = i_sum = m_sum = e_sum = 0.0
    weight_sum = 0.0

    for label, prob in zeroshot_scores.items():
        profile = _ZEROSHOT_TIME_MAP.get(label)
        if profile is None:
            continue
        t_sum += profile[0] * prob
        i_sum += profile[1] * prob
        m_sum += profile[2] * prob
        e_sum += profile[3] * prob
        weight_sum += prob

    if weight_sum < 0.01:
        return None  # can't derive anything

    t = round(t_sum / weight_sum, 2)
    i = round(i_sum / weight_sum, 2)
    m = round(m_sum / weight_sum, 2)
    e = round(e_sum / weight_sum, 2)

    from app.models.medgemma import _score_to_clinical_description

    return {
        "tissue":       {"type": _score_to_clinical_description("tissue", t), "score": t},
        "inflammation": {"type": _score_to_clinical_description("inflammation", i), "score": i},
        "moisture":     {"type": _score_to_clinical_description("moisture", m), "score": m},
        "edge":         {"type": _score_to_clinical_description("edge", e), "score": e},
    }


# ---------------------------------------------------------------------------
# Rule-based contradiction detection
# ---------------------------------------------------------------------------

_POSITIVE_KEYWORDS = [
    "better", "improving", "improvement", "healing", "healed", "good progress",
    "cleaner", "contracting", "less pain", "less drainage", "resolved",
    "granulation", "epithelializing", "looks good", "looks great",
]

_NEGATIVE_KEYWORDS = [
    "worse", "worsening", "deteriorat", "infect", "necrotic", "odor",
    "more pain", "increased", "inflamed", "undermined", "purulent",
    "slough", "dehiscence", "no improvement", "not healing",
]


def rule_based_contradiction(
    trajectory: str, nurse_notes: str,
) -> dict[str, Any] | None:
    """Check for obvious nurse-AI contradiction via keyword matching.

    Returns contradiction dict if detected, None if ambiguous (defer to LLM).
    """
    notes_lower = nurse_notes.lower()

    has_positive = any(kw in notes_lower for kw in _POSITIVE_KEYWORDS)
    has_negative = any(kw in notes_lower for kw in _NEGATIVE_KEYWORDS)

    # Nurse says positive but AI says deteriorating
    if has_positive and not has_negative and trajectory == "deteriorating":
        return {
            "contradiction": True,
            "detail": (
                "Nurse notes indicate improvement while AI assessment shows deterioration. "
                "Clinical review recommended to resolve this discrepancy."
            ),
        }

    # Nurse says negative but AI says improving
    if has_negative and not has_positive and trajectory == "improving":
        return {
            "contradiction": True,
            "detail": (
                "Nurse notes indicate worsening while AI assessment shows improvement. "
                "Clinical review recommended to resolve this discrepancy."
            ),
        }

    # Both positive and negative — ambiguous, let LLM decide
    return None




# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _compute_trajectory(
    current_scores: dict[str, Any],
    previous: dict[str, Any],
    change_score: float,
) -> str:
    """Determine healing trajectory by comparing current and previous TIME scores.

    Returns one of: improving, stable, deteriorating.
    """
    prev_avg = 0.0
    curr_avg = 0.0
    count = 0
    for dim in ("tissue", "inflammation", "moisture", "edge"):
        curr_val = current_scores.get(dim, {}).get("score")
        prev_key = f"{dim}_score"
        prev_val = previous.get(prev_key)
        if curr_val is not None and prev_val is not None:
            curr_avg += curr_val
            prev_avg += prev_val
            count += 1

    if count == 0:
        return "stable"

    curr_avg /= count
    prev_avg /= count
    delta = curr_avg - prev_avg

    # Thresholds
    if delta > 0.05:
        return "improving"
    if delta < -0.05:
        return "deteriorating"
    return "stable"


def _determine_alert(
    trajectory: str,
    time_scores: dict[str, Any],
    contradiction: dict[str, Any],
) -> dict[str, str | None]:
    """Determine alert level and detail string.

    Levels: green, yellow, orange, red.
    """
    scores = [v["score"] for v in time_scores.values()]
    min_score = min(scores) if scores else 1.0
    avg_score = sum(scores) / len(scores) if scores else 1.0

    # Red: any critical dimension or rapid deterioration
    if min_score < 0.2 or (trajectory == "deteriorating" and avg_score < 0.4):
        level = "red"
        detail = "Critical wound status — immediate clinical review required."
    # Orange: deteriorating or contradiction present
    elif trajectory == "deteriorating" or contradiction.get("contradiction"):
        level = "orange"
        details: list[str] = []
        if trajectory == "deteriorating":
            details.append("Wound is deteriorating since last visit.")
        if contradiction.get("contradiction"):
            details.append(f"Contradiction: {contradiction.get('detail', 'N/A')}")
        detail = " ".join(details)
    # Yellow: below-average scores
    elif avg_score < 0.5:
        level = "yellow"
        detail = "Suboptimal healing indicators — consider care plan review."
    else:
        level = "green"
        detail = None

    return {"level": level, "detail": detail}


def _extract_healing_comment(report: str, trajectory: str) -> str:
    """Extract the clinical summary from the model-generated report.

    Falls back to a trajectory-aware comment if extraction fails.
    """
    import re

    # Try to extract "### Clinical Summary" section from markdown report
    match = re.search(
        r"###\s*Clinical Summary\s*\n+(.+?)(?=\n###|\n##|\Z)",
        report,
        re.DOTALL,
    )
    if match:
        summary = match.group(1).strip()
        # Strip non-ASCII garbage (model hallucinations)
        clean = re.sub(r"[^\x20-\x7E]", "", summary).strip()
        # Remove broken possessives left after stripping: "patient'" -> "patient's"
        clean = re.sub(r"(\w)'\s*,", r"\1's", clean)
        if len(clean) < 15:
            clean = ""  # too short after cleaning, use fallback
        # Take only the first sentence if it's too long
        if clean and len(clean) > 120:
            first_sentence = re.split(r"(?<=[.!?])\s", clean, maxsplit=1)
            clean = first_sentence[0]
        if clean:
            return clean

    # Fallback: trajectory-aware comment
    return {
        "improving": "Wound showing improvement since last visit.",
        "stable": "Wound status stable — continue monitoring.",
        "deteriorating": "Wound deteriorating — intervention recommended.",
        "baseline": "Initial assessment — baseline established.",
    }.get(trajectory, "Assessment complete.")


# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

class WoundAgent:
    """Orchestrates the full wound analysis pipeline."""

    def __init__(
        self,
        medgemma: MedGemmaWrapper,
        medsiglip: MedSigLIPWrapper,
        medasr: MedASRWrapper,
        db: Any,  # module-level db helper functions
    ) -> None:
        self.medgemma = medgemma
        self.medsiglip = medsiglip
        self.medasr = medasr
        self.db = db

    def analyze(
        self,
        assessment_id: str,
        image: Image.Image,
        audio_path: str | None = None,
        wound_type: str | None = None,
    ) -> dict[str, Any]:
        """Run the full 8-step analysis pipeline and persist results.

        When wound_type contains "burn", uses burn-specific labels and prompts.
        """

        is_burn = wound_type is not None and "burn" in wound_type.lower()
        logger.info(
            "Starting analysis for assessment %s (wound_type=%s, burn=%s)",
            assessment_id, wound_type, is_burn,
        )

        # Step 1: MedSigLIP — embedding + zero-shot
        labels = BURN_LABELS if is_burn else WOUND_LABELS
        logger.info("Step 1: Computing SigLIP embedding and zero-shot scores (%d labels).", len(labels))
        embedding = self.medsiglip.get_embedding(image)
        zeroshot = self.medsiglip.zero_shot_classify(image, labels)

        # Step 2: MedGemma — TIME classification (fetch assessment first for image_path)
        assessment = self.db.get_assessment(assessment_id)
        if assessment is None:
            raise ValueError(f"Assessment {assessment_id} not found.")
        logger.info("Step 2: Running TIME classification via MedGemma.")
        try:
            time_scores = self.medgemma.classify_time(
                image, image_path=assessment.get("image_path"), wound_type=wound_type,
            )
        except Exception as exc:
            logger.warning("classify_time failed: %s — trying zero-shot fallback.", exc)
            time_scores = None

        # Check for all-zero scores (parsing failure) or total failure
        if time_scores is not None:
            all_zero = all(
                time_scores[d]["score"] == 0.0
                for d in ("tissue", "inflammation", "moisture", "edge")
            )
            if all_zero:
                logger.warning("All TIME scores are 0.0 — likely parsing failure, trying fallback.")
                time_scores = None

        if time_scores is None:
            fallback = zeroshot_to_time_fallback(zeroshot)
            if fallback is not None:
                logger.info("Using MedSigLIP zero-shot fallback for TIME scores.")
                time_scores = fallback
            else:
                # Last resort: use score_to_clinical_description defaults
                from app.models.medgemma import _score_to_clinical_description
                time_scores = {
                    dim: {"type": _score_to_clinical_description(dim, 0.0), "score": 0.0}
                    for dim in ("tissue", "inflammation", "moisture", "edge")
                }

        # Step 3: Retrieve previous assessment for this patient
        patient_id = assessment["patient_id"]
        current_date = assessment["visit_date"]
        previous = self.db.get_latest_assessment(
            patient_id, exclude_id=assessment_id, before_date=current_date
        )

        # Step 4: Compute change score and trajectory
        change_score: float | None = None
        trajectory = "baseline"
        if previous and previous.get("embedding"):
            logger.info("Step 4: Computing trajectory against previous visit (%s).", previous["visit_date"][:10])
            prev_embedding = np.frombuffer(previous["embedding"], dtype=np.float32)
            change_score = float(cosine_distance(embedding, prev_embedding))
            trajectory = _compute_trajectory(time_scores, previous, change_score)
        else:
            logger.info("Step 4: No previous analyzed assessment — marking as baseline.")

        # Step 5: Audio transcription (optional) + text notes
        nurse_notes: str | None = None
        if audio_path:
            logger.info("Step 5: Transcribing nurse audio notes.")
            nurse_notes = self.medasr.transcribe(audio_path)
        else:
            logger.info("Step 5: No audio provided, skipping transcription.")

        # Combine typed text notes with audio transcription
        text_notes = assessment.get("text_notes")
        if text_notes:
            if nurse_notes:
                nurse_notes = f"{nurse_notes}\n\nAdditional typed notes: {text_notes}"
            else:
                nurse_notes = text_notes

        # Step 6: Contradiction detection (rule-based first, then LLM fallback)
        contradiction: dict[str, Any] = {"contradiction": False, "detail": None}
        if nurse_notes and trajectory != "baseline":
            logger.info("Step 6: Checking for contradictions.")
            # Try rule-based detection first (fast, handles LLM blind spots)
            rule_result = rule_based_contradiction(trajectory, nurse_notes)
            if rule_result is not None:
                logger.info("Step 6: Rule-based contradiction detected.")
                contradiction = rule_result
            else:
                # Ambiguous case — defer to LLM
                contradiction = self.medgemma.detect_contradiction(
                    trajectory, nurse_notes, image=image,
                )
        else:
            logger.info("Step 6: Skipping contradiction detection.")

        # Step 7: Report generation
        logger.info("Step 7: Generating clinical report.")
        patient = self.db.get_patient(patient_id)
        report = self.medgemma.generate_report(
            image, time_scores, trajectory, change_score, nurse_notes, contradiction,
            patient_name=patient.get("name") if patient else None,
            wound_type=patient.get("wound_type") if patient else None,
            wound_location=patient.get("wound_location") if patient else None,
            visit_date=current_date,
        )

        # Step 7b: Nurse Q&A (dedicated inference if questions detected)
        if nurse_notes and ('?' in nurse_notes or any(
            kw in nurse_notes.lower()
            for kw in ('should', 'can i', 'do i', 'is it', 'what', 'how', 'when', 'which')
        )):
            logger.info("Step 7b: Answering nurse questions (dedicated call).")
            try:
                nurse_answers = self.medgemma.answer_nurse_questions(
                    nurse_notes, time_scores, image=image,
                )
                if nurse_answers:
                    logger.info("Step 7b: Got %d nurse answers.", len(nurse_answers))
                    guidance = ['', '### Clinical Guidance']
                    guidance.append('*Answers to nurse questions based on wound assessment:*')
                    guidance.append('')
                    for ans in nurse_answers:
                        guidance.append(f'- {ans}')
                    report += '\n' + '\n'.join(guidance)
            except Exception as exc:
                logger.warning("Step 7b: Nurse Q&A failed: %s", exc)
        else:
            logger.info("Step 7b: No nurse questions detected, skipping.")

        # Step 8: Alert determination
        logger.info("Step 8: Determining alert level.")
        alert = _determine_alert(trajectory, time_scores, contradiction)

        # Step 9: Extract healing comment from report
        healing_comment = _extract_healing_comment(report, trajectory)

        # Persist results
        update_data: dict[str, Any] = {
            "tissue_type": time_scores["tissue"]["type"],
            "tissue_score": time_scores["tissue"]["score"],
            "inflammation": time_scores["inflammation"]["type"],
            "inflammation_score": time_scores["inflammation"]["score"],
            "moisture": time_scores["moisture"]["type"],
            "moisture_score": time_scores["moisture"]["score"],
            "edge": time_scores["edge"]["type"],
            "edge_score": time_scores["edge"]["score"],
            "embedding": embedding.tobytes(),
            "zeroshot_scores": json.dumps(zeroshot),
            "nurse_notes": nurse_notes,
            "change_score": change_score,
            "trajectory": trajectory,
            "contradiction_flag": contradiction.get("contradiction", False),
            "contradiction_detail": contradiction.get("detail"),
            "report_text": report,
            "alert_level": alert["level"],
            "alert_detail": alert.get("detail"),
            "healing_comment": healing_comment,
        }
        self.db.update_assessment(assessment_id, update_data)

        logger.info(
            "Analysis complete for %s — trajectory=%s, alert=%s",
            assessment_id,
            trajectory,
            alert["level"],
        )
        return update_data
