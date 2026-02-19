"""API routes — all REST endpoints for the Wound Monitor backend."""

from __future__ import annotations

import html as html_lib
import json
import logging
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse
from PIL import Image

from app import db
from app.config import settings
from app.schemas.wound import (
    AnalysisResult,
    AssessmentImageResponse,
    AssessmentResponse,
    PatientCreate,
    PatientReportInfo,
    PatientReportResponse,
    PatientResponse,
    ReferralCreate,
    ReferralResponse,
    ReferralUpdate,
    TimeClassification,
    TimeScore,
    TrajectoryPoint,
)

logger = logging.getLogger(__name__)
router = APIRouter()

# ---------------------------------------------------------------------------
# Global agent reference — set from main.py after models are loaded
# ---------------------------------------------------------------------------
_agent: Any = None


def set_agent(agent: Any) -> None:
    global _agent
    _agent = agent


def get_agent() -> Any:
    return _agent


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _html_escape(value: str) -> str:
    """Escape a string for safe embedding in HTML."""
    return html_lib.escape(str(value))


def _to_url(path: str | None) -> str | None:
    """Convert a filesystem upload path to a URL path served by the static mount."""
    if not path:
        return None
    prefix = settings.UPLOAD_DIR
    # Normalise: strip trailing slash from prefix
    if not prefix.endswith("/"):
        prefix += "/"
    if path.startswith(prefix):
        return "/uploads/" + path[len(prefix):]
    # Also handle relative ./data/uploads/ form
    alt_prefix = "./data/uploads/"
    if path.startswith(alt_prefix):
        return "/uploads/" + path[len(alt_prefix):]
    return path


def _save_upload(file: UploadFile, subdir: str) -> str:
    """Save an uploaded file to UPLOAD_DIR/<subdir> and return the relative path."""
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    # Strip directory components to prevent path traversal, then add UUID for uniqueness
    raw_name = Path(file.filename).name if file.filename else "upload"
    safe_name = raw_name.replace(" ", "_")
    filename = f"{ts}_{uuid.uuid4().hex[:8]}_{safe_name}"
    dest_dir = os.path.join(settings.UPLOAD_DIR, subdir)
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, filename)
    with open(dest, "wb") as f:
        shutil.copyfileobj(file.file, f)
    return dest


def _assessment_to_response(a: dict[str, Any]) -> AssessmentResponse:
    """Convert a raw DB assessment dict to an AssessmentResponse."""
    time_cls = None
    if a.get("tissue_type") is not None:
        time_cls = TimeClassification(
            tissue=TimeScore(type=a["tissue_type"], score=a["tissue_score"]),
            inflammation=TimeScore(type=a["inflammation"], score=a["inflammation_score"]),
            moisture=TimeScore(type=a["moisture"], score=a["moisture_score"]),
            edge=TimeScore(type=a["edge"], score=a["edge_score"]),
        )

    zeroshot = None
    if a.get("zeroshot_scores"):
        try:
            zeroshot = json.loads(a["zeroshot_scores"])
        except (json.JSONDecodeError, TypeError):
            pass

    # Fetch associated images from assessment_images table
    raw_images = db.get_assessment_images(a["id"])
    images = [
        AssessmentImageResponse(
            id=img["id"],
            image_path=_to_url(img["image_path"]) or img["image_path"],
            is_primary=bool(img["is_primary"]),
            caption=img.get("caption"),
            created_at=img["created_at"],
        )
        for img in raw_images
    ]

    return AssessmentResponse(
        id=a["id"],
        patient_id=a["patient_id"],
        visit_date=a["visit_date"],
        image_path=_to_url(a["image_path"]) or a["image_path"],
        source=a.get("source") or "nurse",
        audio_path=_to_url(a.get("audio_path")),
        text_notes=a.get("text_notes"),
        images=images,
        time_classification=time_cls,
        zeroshot_scores=zeroshot,
        nurse_notes=a.get("nurse_notes"),
        change_score=a.get("change_score"),
        trajectory=a.get("trajectory"),
        contradiction_flag=bool(a.get("contradiction_flag")),
        contradiction_detail=a.get("contradiction_detail"),
        report_text=a.get("report_text"),
        alert_level=a.get("alert_level"),
        alert_detail=a.get("alert_detail"),
        healing_comment=a.get("healing_comment"),
        created_at=a["created_at"],
    )


# ---------------------------------------------------------------------------
# Patient endpoints
# ---------------------------------------------------------------------------

@router.post("/patients", response_model=PatientResponse, status_code=201)
def create_patient(body: PatientCreate) -> PatientResponse:
    patient = db.create_patient(body.model_dump())
    return _patient_response(patient)


@router.get("/patients", response_model=list[PatientResponse])
def list_patients() -> list[PatientResponse]:
    patients = db.list_patients()
    return [_patient_response(p) for p in patients]


@router.get("/patients/{patient_id}", response_model=PatientResponse)
def get_patient(patient_id: str) -> PatientResponse:
    patient = db.get_patient(patient_id)
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found.")
    return _patient_response(patient)


def _patient_response(patient: dict[str, Any]) -> PatientResponse:
    """Enrich a patient dict with latest trajectory/alert and assessment count."""
    assessments = db.get_patient_assessments(patient["id"])
    latest = db.get_latest_assessment(patient["id"])
    return PatientResponse(
        id=patient["id"],
        name=patient["name"],
        age=patient.get("age"),
        sex=patient.get("sex"),
        phone=patient.get("phone"),
        wound_type=patient.get("wound_type"),
        wound_location=patient.get("wound_location"),
        comorbidities=patient.get("comorbidities", []),
        referring_physician=patient.get("referring_physician"),
        referring_physician_specialty=patient.get("referring_physician_specialty"),
        referring_physician_facility=patient.get("referring_physician_facility"),
        referring_physician_phone=patient.get("referring_physician_phone"),
        referring_physician_email=patient.get("referring_physician_email"),
        referring_physician_preferred_contact=patient.get("referring_physician_preferred_contact"),
        patient_token=patient.get("patient_token") or "",
        created_at=patient["created_at"],
        latest_trajectory=latest.get("trajectory") if latest else None,
        latest_alert_level=latest.get("alert_level") if latest else None,
        assessment_count=len(assessments),
        patient_reported_count=db.count_patient_reported(patient["id"]),
    )


# ---------------------------------------------------------------------------
# Assessment endpoints
# ---------------------------------------------------------------------------

@router.post("/assessments", response_model=AssessmentResponse, status_code=201)
def create_assessment(
    patient_id: str = Form(...),
    image: UploadFile = File(...),
    additional_images: list[UploadFile] = File(default=[]),
    audio: UploadFile | None = File(None),
    visit_date: str | None = Form(None),
    text_notes: str | None = Form(None),
) -> AssessmentResponse:
    # Validate patient exists
    patient = db.get_patient(patient_id)
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found.")

    # Save primary image
    image_path = _save_upload(image, f"patients/{patient_id}/images")

    # Save audio if present
    audio_path: str | None = None
    if audio is not None:
        audio_path = _save_upload(audio, f"patients/{patient_id}/audio")

    data = {
        "patient_id": patient_id,
        "image_path": image_path,
        "audio_path": audio_path,
        "visit_date": visit_date,
        "text_notes": text_notes,
    }
    assessment = db.create_assessment(data)

    # Insert primary image into assessment_images table
    db.add_assessment_image(assessment["id"], image_path, is_primary=True)

    # Save additional images
    for extra_img in additional_images:
        extra_path = _save_upload(extra_img, f"patients/{patient_id}/images")
        db.add_assessment_image(assessment["id"], extra_path, is_primary=False)

    return _assessment_to_response(assessment)


@router.post("/assessments/{assessment_id}/analyze", response_model=AnalysisResult)
def analyze_assessment(assessment_id: str) -> AnalysisResult:
    agent = get_agent()
    if agent is None:
        raise HTTPException(
            status_code=503,
            detail="Models not loaded. Set WOUNDCHRONO_MOCK_MODELS=true for dev mode or wait for startup.",
        )

    assessment = db.get_assessment(assessment_id)
    if assessment is None:
        raise HTTPException(status_code=404, detail="Assessment not found.")

    # Load image
    image_path = assessment["image_path"]
    if not os.path.isfile(image_path):
        raise HTTPException(status_code=404, detail=f"Image file not found: {image_path}")
    try:
        image = Image.open(image_path).convert("RGB")
    except Exception as exc:
        logger.warning("Failed to open image %s: %s", image_path, exc)
        raise HTTPException(
            status_code=422, detail=f"Cannot open image file: {exc}"
        ) from exc

    audio_path = assessment.get("audio_path")
    if audio_path and not os.path.isfile(audio_path):
        logger.warning("Audio file not found, skipping: %s", audio_path)
        audio_path = None

    # Fetch patient wound_type for conditional prompt routing
    patient = db.get_patient(assessment["patient_id"])
    wound_type = patient.get("wound_type") if patient else None

    try:
        result = agent.analyze(assessment_id, image, audio_path=audio_path, wound_type=wound_type)
    except Exception as exc:
        logger.exception("Analysis failed for assessment %s", assessment_id)
        raise HTTPException(status_code=500, detail=str(exc)) from exc

    # Build response
    time_cls = TimeClassification(
        tissue=TimeScore(type=result["tissue_type"], score=result["tissue_score"]),
        inflammation=TimeScore(type=result["inflammation"], score=result["inflammation_score"]),
        moisture=TimeScore(type=result["moisture"], score=result["moisture_score"]),
        edge=TimeScore(type=result["edge"], score=result["edge_score"]),
    )
    zeroshot = json.loads(result["zeroshot_scores"]) if isinstance(result["zeroshot_scores"], str) else result["zeroshot_scores"]

    return AnalysisResult(
        assessment_id=assessment_id,
        time_classification=time_cls,
        zeroshot_scores=zeroshot,
        trajectory=result.get("trajectory", "baseline"),
        change_score=result.get("change_score"),
        contradiction_flag=bool(result.get("contradiction_flag")),
        contradiction_detail=result.get("contradiction_detail"),
        report_text=result.get("report_text", ""),
        alert_level=result.get("alert_level", "green"),
        alert_detail=result.get("alert_detail"),
        healing_comment=result.get("healing_comment"),
    )


@router.get("/patients/{patient_id}/assessments", response_model=list[AssessmentResponse])
def list_patient_assessments(patient_id: str) -> list[AssessmentResponse]:
    patient = db.get_patient(patient_id)
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found.")
    assessments = db.get_patient_assessments(patient_id)
    return [_assessment_to_response(a) for a in assessments]


@router.get("/assessments/{assessment_id}", response_model=AssessmentResponse)
def get_assessment(assessment_id: str) -> AssessmentResponse:
    assessment = db.get_assessment(assessment_id)
    if assessment is None:
        raise HTTPException(status_code=404, detail="Assessment not found.")
    return _assessment_to_response(assessment)


@router.post("/assessments/{assessment_id}/images", response_model=AssessmentResponse)
def add_assessment_images(
    assessment_id: str,
    images: list[UploadFile] = File(...),
) -> AssessmentResponse:
    """Add additional images to an existing assessment."""
    assessment = db.get_assessment(assessment_id)
    if assessment is None:
        raise HTTPException(status_code=404, detail="Assessment not found.")
    patient_id = assessment["patient_id"]
    for img in images:
        path = _save_upload(img, f"patients/{patient_id}/images")
        db.add_assessment_image(assessment_id, path, is_primary=False)
    return _assessment_to_response(db.get_assessment(assessment_id))


# ---------------------------------------------------------------------------
# Trajectory endpoint
# ---------------------------------------------------------------------------

@router.get("/patients/{patient_id}/trajectory", response_model=list[TrajectoryPoint])
def get_trajectory(patient_id: str) -> list[TrajectoryPoint]:
    patient = db.get_patient(patient_id)
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found.")

    assessments = db.get_patient_assessments(patient_id)
    points: list[TrajectoryPoint] = []
    for a in assessments:
        points.append(
            TrajectoryPoint(
                visit_date=a["visit_date"],
                tissue_score=a.get("tissue_score"),
                inflammation_score=a.get("inflammation_score"),
                moisture_score=a.get("moisture_score"),
                edge_score=a.get("edge_score"),
                trajectory=a.get("trajectory"),
                change_score=a.get("change_score"),
            )
        )
    return points


# ---------------------------------------------------------------------------
# Patient self-reporting endpoints
# ---------------------------------------------------------------------------

@router.get("/patient-report/{token}/info", response_model=PatientReportInfo)
def patient_report_info(token: str) -> PatientReportInfo:
    """Public endpoint — returns minimal patient info for the upload page."""
    patient = db.get_patient_by_token(token)
    if patient is None:
        raise HTTPException(status_code=404, detail="Invalid link.")
    # Mask the name for privacy: first char + "***"
    name = patient.get("name") or ""
    masked = name[0] + "***" if name else "Patient"
    return PatientReportInfo(
        patient_name=masked,
        wound_type=patient.get("wound_type"),
        wound_location=patient.get("wound_location"),
    )


@router.post("/patient-report/{token}", response_model=PatientReportResponse, status_code=201)
def patient_report_upload(
    token: str,
    image: UploadFile = File(...),
    note: str | None = Form(None),
) -> PatientReportResponse:
    """Public endpoint — patient uploads a wound photo."""
    patient = db.get_patient_by_token(token)
    if patient is None:
        raise HTTPException(status_code=404, detail="Invalid link.")

    patient_id = patient["id"]
    image_path = _save_upload(image, f"patients/{patient_id}/images")

    data = {
        "patient_id": patient_id,
        "image_path": image_path,
        "source": "patient",
        "text_notes": note,
    }
    assessment = db.create_assessment(data)
    db.add_assessment_image(assessment["id"], image_path, is_primary=True)

    return PatientReportResponse(
        assessment_id=assessment["id"],
        message="Photo received. Your nurse will be notified.",
    )


# ---------------------------------------------------------------------------
# Referral endpoints
# ---------------------------------------------------------------------------

_VALID_URGENCY = {"routine", "urgent", "emergency"}
_VALID_REFERRAL_STATUS = {"pending", "sent", "reviewed"}


@router.post("/referrals", response_model=ReferralResponse, status_code=201)
def create_referral(body: ReferralCreate) -> ReferralResponse:
    # Validate foreign keys exist
    patient = db.get_patient(body.patient_id)
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found.")
    assessment = db.get_assessment(body.assessment_id)
    if assessment is None:
        raise HTTPException(status_code=404, detail="Assessment not found.")
    if body.urgency not in _VALID_URGENCY:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid urgency. Must be one of: {', '.join(sorted(_VALID_URGENCY))}",
        )
    referral = db.create_referral(body.model_dump())
    return ReferralResponse(**referral)


@router.get("/patients/{patient_id}/referrals", response_model=list[ReferralResponse])
def list_patient_referrals(patient_id: str) -> list[ReferralResponse]:
    patient = db.get_patient(patient_id)
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found.")
    referrals = db.get_referrals_for_patient(patient_id)
    return [ReferralResponse(**r) for r in referrals]


@router.get("/referrals/{referral_id}/summary", response_class=HTMLResponse)
def get_referral_summary(referral_id: str) -> HTMLResponse:
    referral = db.get_referral(referral_id)
    if referral is None:
        raise HTTPException(status_code=404, detail="Referral not found.")

    assessment = db.get_assessment(referral["assessment_id"])
    if assessment is None:
        raise HTTPException(status_code=404, detail="Assessment not found.")

    patient = db.get_patient(referral["patient_id"])
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found.")

    # Parse comorbidities (may already be a list from get_patient)
    comorbidities = patient.get("comorbidities", [])
    if isinstance(comorbidities, str):
        try:
            comorbidities = json.loads(comorbidities)
        except (json.JSONDecodeError, TypeError):
            comorbidities = []

    # Compute TIME scores
    time_rows = ""
    score_sum = 0.0
    score_count = 0
    for dimension, type_key, score_key in [
        ("Tissue", "tissue_type", "tissue_score"),
        ("Inflammation", "inflammation", "inflammation_score"),
        ("Moisture", "moisture", "moisture_score"),
        ("Edge", "edge", "edge_score"),
    ]:
        dim_type = assessment.get(type_key) or "N/A"
        dim_score = assessment.get(score_key)
        if dim_score is not None:
            score_sum += dim_score
            score_count += 1
            score_display = f"{dim_score:.1f}/10"
        else:
            score_display = "N/A"
        time_rows += f"<tr><td>{dimension}</td><td>{_html_escape(dim_type)}</td><td>{score_display}</td></tr>\n"

    overall_score = f"{(score_sum / score_count):.1f}/10" if score_count > 0 else "N/A"

    # Trajectory and change
    trajectory = _html_escape(assessment.get("trajectory") or "N/A")
    change_score = assessment.get("change_score")
    change_display = f"{change_score:+.2f}" if change_score is not None else "N/A"

    # Alert
    alert_level = _html_escape(assessment.get("alert_level") or "N/A")
    alert_detail = _html_escape(assessment.get("alert_detail") or "")

    # Report
    report_text = _html_escape(assessment.get("report_text") or "No AI report available.")

    # Referral notes
    nurse_notes = _html_escape(referral.get("referral_notes") or "None provided.")

    # Urgency
    urgency = _html_escape(referral.get("urgency") or "routine")

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Wound Monitor Clinical Referral</title>
<style>
  body {{ font-family: Arial, Helvetica, sans-serif; margin: 2em; color: #222; line-height: 1.5; }}
  h1 {{ color: #1a5276; border-bottom: 2px solid #1a5276; padding-bottom: 0.3em; }}
  h2 {{ color: #2c3e50; margin-top: 1.5em; }}
  table {{ border-collapse: collapse; width: 100%; margin: 0.5em 0; }}
  th, td {{ border: 1px solid #bbb; padding: 0.5em 0.8em; text-align: left; }}
  th {{ background: #eaf2f8; }}
  .alert-red {{ color: #c0392b; font-weight: bold; }}
  .alert-orange {{ color: #e67e22; font-weight: bold; }}
  .alert-yellow {{ color: #f1c40f; font-weight: bold; }}
  .alert-green {{ color: #27ae60; font-weight: bold; }}
  .urgency-emergency {{ color: #c0392b; font-weight: bold; text-transform: uppercase; }}
  .urgency-urgent {{ color: #e67e22; font-weight: bold; text-transform: uppercase; }}
  .urgency-routine {{ color: #2c3e50; }}
  .report {{ background: #f9f9f9; border-left: 4px solid #1a5276; padding: 1em; white-space: pre-wrap; }}
  .footer {{ margin-top: 2em; padding-top: 1em; border-top: 1px solid #ccc; font-size: 0.85em; color: #888; }}
</style>
</head>
<body>

<h1>Wound Monitor &mdash; Clinical Referral</h1>

<h2>Patient Information</h2>
<table>
  <tr><th>Name</th><td>{_html_escape(patient.get("name", ""))}</td></tr>
  <tr><th>Age</th><td>{patient.get("age") or "N/A"}</td></tr>
  <tr><th>Wound Type</th><td>{_html_escape(patient.get("wound_type") or "N/A")}</td></tr>
  <tr><th>Wound Location</th><td>{_html_escape(patient.get("wound_location") or "N/A")}</td></tr>
  <tr><th>Comorbidities</th><td>{_html_escape(", ".join(comorbidities) if comorbidities else "None")}</td></tr>
</table>

<h2>Assessment</h2>
<p><strong>Date:</strong> {_html_escape(assessment.get("visit_date") or "N/A")}</p>

<h2>TIME Scores</h2>
<table>
  <tr><th>Dimension</th><th>Type</th><th>Score</th></tr>
  {time_rows}
</table>
<p><strong>Overall Healing Score:</strong> {overall_score}</p>

<h2>Trajectory &amp; Change</h2>
<p><strong>Trajectory:</strong> {trajectory}</p>
<p><strong>Change Score:</strong> {change_display}</p>

<h2>Alert</h2>
<p class="alert-{alert_level.lower()}"><strong>Level:</strong> {alert_level}</p>
<p>{alert_detail}</p>

<h2>AI Clinical Report</h2>
<div class="report">{report_text}</div>

<h2>Nurse Notes</h2>
<p>{nurse_notes}</p>

<h2>Urgency</h2>
<p class="urgency-{urgency.lower()}">{urgency.capitalize()}</p>

<div class="footer">
  Generated by Wound Monitor AI &mdash; For clinical review only
</div>

</body>
</html>"""

    return HTMLResponse(content=html)


@router.patch("/referrals/{referral_id}", response_model=ReferralResponse)
def update_referral(referral_id: str, body: ReferralUpdate) -> ReferralResponse:
    referral = db.get_referral(referral_id)
    if referral is None:
        raise HTTPException(status_code=404, detail="Referral not found.")
    if body.status not in _VALID_REFERRAL_STATUS:
        raise HTTPException(
            status_code=422,
            detail=f"Invalid status. Must be one of: {', '.join(sorted(_VALID_REFERRAL_STATUS))}",
        )
    updated = db.update_referral(referral_id, body.model_dump(exclude_unset=True))
    if updated is None:
        raise HTTPException(status_code=404, detail="Referral not found after update.")
    return ReferralResponse(**updated)
