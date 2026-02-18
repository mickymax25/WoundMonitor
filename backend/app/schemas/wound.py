"""Pydantic models for request / response validation."""

from __future__ import annotations

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Patients
# ---------------------------------------------------------------------------

class PatientCreate(BaseModel):
    name: str
    age: int | None = None
    sex: str | None = None  # male | female
    phone: str | None = None
    wound_type: str | None = None  # diabetic_ulcer | pressure_ulcer | venous_ulcer | other
    wound_location: str | None = None
    comorbidities: list[str] = []
    referring_physician: str | None = None
    referring_physician_specialty: str | None = None
    referring_physician_facility: str | None = None
    referring_physician_phone: str | None = None
    referring_physician_email: str | None = None
    referring_physician_preferred_contact: str | None = None  # phone | email | whatsapp


class PatientResponse(BaseModel):
    id: str
    name: str
    age: int | None = None
    sex: str | None = None
    phone: str | None = None
    wound_type: str | None = None
    wound_location: str | None = None
    comorbidities: list[str] = []
    referring_physician: str | None = None
    referring_physician_specialty: str | None = None
    referring_physician_facility: str | None = None
    referring_physician_phone: str | None = None
    referring_physician_email: str | None = None
    referring_physician_preferred_contact: str | None = None
    patient_token: str = ""
    created_at: str
    latest_trajectory: str | None = None
    latest_alert_level: str | None = None
    assessment_count: int = 0
    patient_reported_count: int = 0


# ---------------------------------------------------------------------------
# TIME classification
# ---------------------------------------------------------------------------

class TimeScore(BaseModel):
    type: str
    score: float


class TimeClassification(BaseModel):
    tissue: TimeScore
    inflammation: TimeScore
    moisture: TimeScore
    edge: TimeScore


# ---------------------------------------------------------------------------
# Assessments
# ---------------------------------------------------------------------------

class AssessmentCreate(BaseModel):
    patient_id: str
    visit_date: str | None = None  # ISO format, defaults to now


class AssessmentImageResponse(BaseModel):
    id: str
    image_path: str
    is_primary: bool
    caption: str | None = None
    created_at: str


class AssessmentResponse(BaseModel):
    id: str
    patient_id: str
    visit_date: str
    image_path: str
    source: str = "nurse"
    audio_path: str | None = None
    text_notes: str | None = None
    images: list[AssessmentImageResponse] = []
    time_classification: TimeClassification | None = None
    zeroshot_scores: dict[str, float] | None = None
    nurse_notes: str | None = None
    change_score: float | None = None
    trajectory: str | None = None
    contradiction_flag: bool = False
    contradiction_detail: str | None = None
    report_text: str | None = None
    alert_level: str | None = None
    alert_detail: str | None = None
    created_at: str


# ---------------------------------------------------------------------------
# Trajectory
# ---------------------------------------------------------------------------

class TrajectoryPoint(BaseModel):
    visit_date: str
    tissue_score: float | None = None
    inflammation_score: float | None = None
    moisture_score: float | None = None
    edge_score: float | None = None
    trajectory: str | None = None
    change_score: float | None = None


# ---------------------------------------------------------------------------
# Analysis result (returned after /analyze)
# ---------------------------------------------------------------------------

class AnalysisResult(BaseModel):
    assessment_id: str
    time_classification: TimeClassification
    zeroshot_scores: dict[str, float]
    trajectory: str
    change_score: float | None = None
    contradiction_flag: bool = False
    contradiction_detail: str | None = None
    report_text: str
    alert_level: str
    alert_detail: str | None = None


# ---------------------------------------------------------------------------
# Referrals
# ---------------------------------------------------------------------------

class ReferralCreate(BaseModel):
    assessment_id: str
    patient_id: str
    urgency: str = "routine"  # routine | urgent | emergency
    physician_name: str | None = None
    physician_contact: str | None = None
    referral_notes: str | None = None


class ReferralResponse(BaseModel):
    id: str
    assessment_id: str
    patient_id: str
    urgency: str
    physician_name: str | None = None
    physician_contact: str | None = None
    referral_notes: str | None = None
    status: str
    created_at: str


class ReferralUpdate(BaseModel):
    status: str  # pending | sent | reviewed


# ---------------------------------------------------------------------------
# Patient self-reporting
# ---------------------------------------------------------------------------

class PatientReportInfo(BaseModel):
    patient_name: str
    wound_type: str | None = None
    wound_location: str | None = None


class PatientReportResponse(BaseModel):
    assessment_id: str
    message: str
