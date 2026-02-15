"""API routes — all REST endpoints for the WoundChrono backend."""

from __future__ import annotations

import json
import logging
import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from PIL import Image

from app import db
from app.config import settings
from app.schemas.wound import (
    AnalysisResult,
    AssessmentResponse,
    PatientCreate,
    PatientResponse,
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

    return AssessmentResponse(
        id=a["id"],
        patient_id=a["patient_id"],
        visit_date=a["visit_date"],
        image_path=a["image_path"],
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
        wound_type=patient.get("wound_type"),
        wound_location=patient.get("wound_location"),
        comorbidities=patient.get("comorbidities", []),
        created_at=patient["created_at"],
        latest_trajectory=latest.get("trajectory") if latest else None,
        latest_alert_level=latest.get("alert_level") if latest else None,
        assessment_count=len(assessments),
    )


# ---------------------------------------------------------------------------
# Assessment endpoints
# ---------------------------------------------------------------------------

@router.post("/assessments", response_model=AssessmentResponse, status_code=201)
def create_assessment(
    patient_id: str = Form(...),
    image: UploadFile = File(...),
    audio: UploadFile | None = File(None),
    visit_date: str | None = Form(None),
) -> AssessmentResponse:
    # Validate patient exists
    patient = db.get_patient(patient_id)
    if patient is None:
        raise HTTPException(status_code=404, detail="Patient not found.")

    # Save image
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
    }
    assessment = db.create_assessment(data)
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

    try:
        result = agent.analyze(assessment_id, image, audio_path=audio_path)
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
