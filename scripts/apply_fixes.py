"""Apply two fixes to WoundChrono backend:

1. All-zero fallback: when TIME parsing fails, use MedSigLIP zero-shot scores
   to derive approximate TIME scores instead of returning 0.0 everywhere.

2. Rule-based contradiction pre-check: detect nurse-AI contradiction via
   keyword matching before falling back to the LLM.

Run on the VM:
    python3 ~/WoundChrono/apply_fixes.py
"""

from __future__ import annotations

from pathlib import Path

BACKEND = Path.home() / "WoundChrono" / "backend" / "app"


def patch_wound_agent():
    """Add zero-shot fallback and rule-based contradiction to wound_agent.py."""
    p = BACKEND / "agents" / "wound_agent.py"
    text = p.read_text()

    if "zeroshot_to_time_fallback" in text:
        print("wound_agent.py: already patched, skipping.")
        return

    # 1. Add the fallback function after the imports
    fallback_function = '''

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

'''

    # Insert after the existing imports block
    text = text.replace(
        "logger = logging.getLogger(__name__)",
        "logger = logging.getLogger(__name__)" + fallback_function,
    )

    # 2. Add fallback after classify_time in the analyze method
    old_classify = '''        time_scores = self.medgemma.classify_time(
            image, image_path=assessment.get("image_path"), wound_type=wound_type,
        )'''

    new_classify = '''        try:
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
                }'''

    text = text.replace(old_classify, new_classify)

    # 3. Add rule-based contradiction before LLM call
    old_contradiction = '''        # Step 6: Contradiction detection
        contradiction: dict[str, Any] = {"contradiction": False, "detail": None}
        if nurse_notes and trajectory != "baseline":
            logger.info("Step 6: Checking for contradictions.")
            contradiction = self.medgemma.detect_contradiction(
                trajectory, nurse_notes, image=image,
            )
        else:
            logger.info("Step 6: Skipping contradiction detection.")'''

    new_contradiction = '''        # Step 6: Contradiction detection (rule-based first, then LLM fallback)
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
            logger.info("Step 6: Skipping contradiction detection.")'''

    text = text.replace(old_contradiction, new_contradiction)

    p.write_text(text)
    print("wound_agent.py: patched with zero-shot fallback + rule-based contradiction.")


if __name__ == "__main__":
    patch_wound_agent()
    print("\nDone. Restart backend to apply changes.")
