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
# 0 = worst, 1 = best — profiles span the full clinical range
# "undermined edges" is SigLIP's catch-all for uncertain wounds → moderate profile
_ZEROSHOT_TIME_MAP: dict[str, tuple[float, float, float, float]] = {
    "healthy granulating wound":              (0.90, 0.90, 0.80, 0.85),
    "infected wound with purulent discharge": (0.15, 0.05, 0.25, 0.15),
    "necrotic wound tissue":                  (0.05, 0.25, 0.20, 0.10),
    "wound with fibrin slough":               (0.30, 0.50, 0.45, 0.35),
    "epithelializing wound edge":             (0.80, 0.85, 0.75, 0.95),
    "dry wound bed":                          (0.40, 0.60, 0.10, 0.40),
    "wound with excessive exudate":           (0.25, 0.20, 0.05, 0.20),
    "wound with undermined edges":            (0.40, 0.50, 0.45, 0.25),
}

# Burn-specific profiles
_ZEROSHOT_BURN_TIME_MAP: dict[str, tuple[float, float, float, float]] = {
    "superficial partial-thickness burn":     (0.65, 0.55, 0.60, 0.70),
    "deep partial-thickness burn":            (0.35, 0.30, 0.40, 0.35),
    "full-thickness burn with eschar":        (0.05, 0.20, 0.15, 0.05),
    "burn wound with active infection":       (0.15, 0.05, 0.20, 0.15),
    "clean granulating burn wound":           (0.70, 0.75, 0.65, 0.60),
    "re-epithelializing burn wound":          (0.80, 0.85, 0.75, 0.90),
    "healed burn with hypertrophic scarring": (0.90, 0.90, 0.85, 0.95),
    "burn wound with graft integration":      (0.60, 0.65, 0.55, 0.50),
}

# Temperature for sharpening softmax probabilities (lower = more peaked)
_ZEROSHOT_TEMPERATURE = 0.1


def zeroshot_to_time_fallback(zeroshot_scores: dict[str, float]) -> dict[str, Any]:
    """Derive TIME scores from MedSigLIP zero-shot classification.

    Applies temperature scaling to amplify small probability differences,
    then computes weighted average of clinical profiles.
    Returns scores in canonical format: {dim: {"type": str, "score": float}}.
    """
    import math

    # Pick the right profile map based on labels present
    time_map = _ZEROSHOT_TIME_MAP
    if any("burn" in label.lower() for label in zeroshot_scores):
        # Check if burn labels dominate
        burn_count = sum(1 for l in zeroshot_scores if "burn" in l.lower())
        if burn_count >= len(zeroshot_scores) // 2:
            time_map = _ZEROSHOT_BURN_TIME_MAP

    # Temperature-scaled softmax re-weighting
    matched = [(label, prob) for label, prob in zeroshot_scores.items()
               if label in time_map]
    if not matched:
        return None

    # Apply temperature scaling: divide log-probs by temperature, re-softmax
    log_probs = [math.log(max(p, 1e-10)) / _ZEROSHOT_TEMPERATURE for _, p in matched]
    max_lp = max(log_probs)
    exp_probs = [math.exp(lp - max_lp) for lp in log_probs]
    total = sum(exp_probs)
    weights = [ep / total for ep in exp_probs]

    t_sum = i_sum = m_sum = e_sum = 0.0
    for (label, _), w in zip(matched, weights):
        profile = time_map[label]
        t_sum += profile[0] * w
        i_sum += profile[1] * w
        m_sum += profile[2] * w
        e_sum += profile[3] * w

    t = round(t_sum, 2)
    i = round(i_sum, 2)
    m = round(m_sum, 2)
    e = round(e_sum, 2)

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
    critical_flags: dict[str, bool] | None = None,
) -> dict[str, str | None]:
    """Determine alert level and detail string using BWAT total (13-65).

    BWAT thresholds (clinically calibrated):
      13-20  → minimal (green)
      21-33  → mild (green)
      34-46  → moderate (yellow)
      47-55  → severe (orange)
      56-65  → critical (red)

    Trajectory and contradictions can escalate the level by one step.
    Levels: green, yellow, orange, red.
    """
    bwat = time_scores.get("_bwat", {})
    bwat_total = bwat.get("total", 0) if bwat else 0

    # Critical visual flags override everything
    if critical_flags:
        flagged = [k for k, v in critical_flags.items() if v]
        if flagged:
            return {
                "level": "red",
                "detail": f"Critical visual flag detected: {', '.join(flagged)}.",
            }

    # Determine base level from BWAT score
    if bwat_total >= 56:
        level = "red"
        detail = "Critical wound status — immediate clinical review required."
    elif bwat_total >= 47:
        level = "orange"
        detail = "Severe wound — specialist evaluation recommended."
    elif bwat_total >= 34:
        level = "yellow"
        detail = "Moderate wound — consider care plan review."
    else:
        level = "green"
        detail = None

    # Escalate if deteriorating trajectory
    if trajectory == "deteriorating":
        if level == "green":
            level = "yellow"
            detail = "Wound is deteriorating since last visit."
        elif level == "yellow":
            level = "orange"
            detail = "Wound is deteriorating — reassess interventions."
        elif level == "orange":
            level = "red"
            detail = "Critical — wound deteriorating with severe BWAT score."

    # Escalate if contradiction detected
    if contradiction.get("contradiction"):
        contradiction_msg = f"Contradiction: {contradiction.get('detail', 'N/A')}"
        if level == "green":
            level = "yellow"
            detail = contradiction_msg
        elif level == "yellow":
            level = "orange"
            detail = f"Moderate wound with contradiction. {contradiction_msg}"
        elif detail:
            detail = f"{detail} {contradiction_msg}"

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

        # Step 1b: Critical visual red flags (independent of scoring)
        red_flags: dict[str, bool] = {}
        try:
            logger.info("Step 1b: Detecting critical visual flags.")
            red_flags = self.medgemma.detect_red_flags(image)
        except Exception as exc:
            logger.warning("Red-flag detection failed: %s", exc)
        critical_flags = {k: v for k, v in red_flags.items() if v}
        if critical_flags:
            logger.warning("Critical visual flags detected: %s", list(critical_flags.keys()))

        # Step 2: TIME classification via MedGemma VLM (primary) with SigLIP fallback
        assessment = self.db.get_assessment(assessment_id)
        if assessment is None:
            raise ValueError(f"Assessment {assessment_id} not found.")

        from app.models.medgemma import _score_to_clinical_description

        # Primary: Evidence-first BWAT (observations -> deterministic scoring)
        try:
            logger.info("Step 2: Extracting observations + scoring BWAT.")
            time_scores = self.medgemma.classify_time_from_observations(
                image,
                image_path=assessment.get("image_path"),
                wound_type=wound_type,
                notes=assessment.get("text_notes"),
                red_flags=red_flags,
            )
        except Exception as exc:
            logger.warning(
                "Observation-first BWAT failed: %s — falling back to direct BWAT scoring.",
                exc,
            )
            from app.models.medgemma import bwat_from_red_flags
            flag_fallback = bwat_from_red_flags(red_flags)
            if flag_fallback is not None:
                logger.info("Step 2 fallback: Using critical-flag BWAT override.")
                time_scores = flag_fallback
            else:
                try:
                    logger.info("Step 2 fallback: Computing BWAT via MedGemma VLM.")
                    time_scores = self.medgemma.classify_time(
                        image, image_path=assessment.get("image_path"), wound_type=wound_type,
                    )
                except Exception as exc2:
                    logger.warning("MedGemma BWAT scoring failed: %s — falling back to SigLIP.", exc2)
                    # Fallback: SigLIP per-dimension zero-shot
                    try:
                        dim_scores = self.medsiglip.classify_time_dimensions(image)
                        time_scores = {
                            dim: {
                                "type": _score_to_clinical_description(dim, dim_scores[dim]),
                                "score": dim_scores[dim],
                            }
                            for dim in ("tissue", "inflammation", "moisture", "edge")
                        }
                    except Exception as exc3:
                        logger.warning("SigLIP fallback also failed: %s — using zero-shot fallback.", exc3)
                        time_scores = zeroshot_to_time_fallback(zeroshot)
                        if time_scores is None:
                            time_scores = {
                                dim: {"type": _score_to_clinical_description(dim, 0.0), "score": 0.0}
                                for dim in ("tissue", "inflammation", "moisture", "edge")
                            }

        # Step 2b: Ensure BWAT data exists — estimate from TIME if missing
        all_zero = all(
            time_scores.get(d, {}).get("score", 0) == 0
            for d in ("tissue", "inflammation", "moisture", "edge")
        )
        has_bwat = "_bwat" in time_scores and time_scores["_bwat"].get("total", 0) > 0

        if not has_bwat and not all_zero:
            # We have non-zero TIME scores but no BWAT → estimate BWAT from TIME
            from app.models.medgemma import time_scores_to_bwat_estimate
            bwat_est = time_scores_to_bwat_estimate(time_scores)
            if bwat_est:
                logger.info(
                    "Step 2b: BWAT estimated from TIME scores (total=%d).",
                    bwat_est["_bwat"]["total"],
                )
                time_scores["_bwat"] = bwat_est["_bwat"]
                for dim in ("tissue", "inflammation", "moisture", "edge"):
                    if dim in bwat_est and dim in time_scores:
                        time_scores[dim]["bwat_composite"] = bwat_est[dim].get("bwat_composite")
                        time_scores[dim]["bwat_items"] = bwat_est[dim].get("bwat_items")
        elif not has_bwat and all_zero:
            # All TIME scores are zero (total safety filter failure)
            # Try SigLIP zero-shot fallback for BWAT estimation
            logger.warning("Step 2b: All TIME scores are zero — trying SigLIP for BWAT estimation.")
            fallback_time = zeroshot_to_time_fallback(zeroshot)
            if fallback_time and any(
                fallback_time.get(d, {}).get("score", 0) > 0
                for d in ("tissue", "inflammation", "moisture", "edge")
            ):
                from app.models.medgemma import time_scores_to_bwat_estimate
                bwat_est = time_scores_to_bwat_estimate(fallback_time)
                if bwat_est:
                    logger.info(
                        "Step 2b: BWAT estimated from SigLIP fallback (total=%d).",
                        bwat_est["_bwat"]["total"],
                    )
                    # Update TIME scores with SigLIP values
                    for dim in ("tissue", "inflammation", "moisture", "edge"):
                        if dim in fallback_time:
                            time_scores[dim] = fallback_time[dim]
                        if dim in bwat_est:
                            time_scores[dim]["bwat_composite"] = bwat_est[dim].get("bwat_composite")
                            time_scores[dim]["bwat_items"] = bwat_est[dim].get("bwat_items")
                    time_scores["_bwat"] = bwat_est["_bwat"]
            else:
                logger.warning("Step 2b: SigLIP fallback also produced zeros — BWAT unavailable.")

        # Step 3: Retrieve previous assessment for this patient
        patient_id = assessment["patient_id"]
        current_date = assessment["visit_date"]
        previous = self.db.get_latest_assessment(
            patient_id, exclude_id=assessment_id, before_date=current_date
        )

        # Step 4: Compute change score and trajectory
        change_score: float | None = None
        trajectory = "baseline"
        previous_visit_date: str | None = None
        previous_healing_score: float | None = None
        if previous and previous.get("embedding"):
            logger.info("Step 4: Computing trajectory against previous visit (%s).", previous["visit_date"][:10])
            prev_embedding = np.frombuffer(previous["embedding"], dtype=np.float32)
            change_score = float(cosine_distance(embedding, prev_embedding))
            trajectory = _compute_trajectory(time_scores, previous, change_score)
            previous_visit_date = previous.get("visit_date")
            # Compute previous healing score (average of TIME dimensions)
            prev_scores = [
                previous.get(f"{dim}_score")
                for dim in ("tissue", "inflammation", "moisture", "edge")
            ]
            prev_valid = [s for s in prev_scores if s is not None]
            if prev_valid:
                previous_healing_score = round(sum(prev_valid) / len(prev_valid) * 10)
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
            critical_flags=critical_flags,
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
        alert = _determine_alert(trajectory, time_scores, contradiction, critical_flags=critical_flags)

        # Step 9: Extract healing comment from report
        healing_comment = _extract_healing_comment(report, trajectory)

        # Extract BWAT data if available
        bwat = time_scores.get("_bwat", {})
        critical_mode = bool(critical_flags)

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
            "previous_visit_date": previous_visit_date,
            "previous_healing_score": previous_healing_score,
            "bwat_total": bwat.get("total"),
            "bwat_size": bwat.get("size"),
            "bwat_depth": bwat.get("depth"),
            "bwat_items": json.dumps(bwat.get("items", {})) if bwat.get("items") else None,
            "bwat_description": bwat.get("description"),
            "critical_mode": critical_mode,
        }
        self.db.update_assessment(assessment_id, update_data)

        logger.info(
            "Analysis complete for %s — trajectory=%s, alert=%s",
            assessment_id,
            trajectory,
            alert["level"],
        )
        return update_data
