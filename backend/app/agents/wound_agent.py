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
        time_scores = self.medgemma.classify_time(
            image, image_path=assessment.get("image_path"), wound_type=wound_type,
        )

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

        # Step 6: Contradiction detection
        contradiction: dict[str, Any] = {"contradiction": False, "detail": None}
        if nurse_notes and trajectory != "baseline":
            logger.info("Step 6: Checking for contradictions.")
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

        # Step 8: Alert determination
        logger.info("Step 8: Determining alert level.")
        alert = _determine_alert(trajectory, time_scores, contradiction)

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
        }
        self.db.update_assessment(assessment_id, update_data)

        logger.info(
            "Analysis complete for %s — trajectory=%s, alert=%s",
            assessment_id,
            trajectory,
            alert["level"],
        )
        return update_data
