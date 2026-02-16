"""SQLite database layer — thin wrapper around sqlite3, no ORM."""

from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from app.config import settings

_SCHEMA = """
CREATE TABLE IF NOT EXISTS patients (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    age INTEGER,
    wound_type TEXT,
    wound_location TEXT,
    comorbidities TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS assessments (
    id TEXT PRIMARY KEY,
    patient_id TEXT NOT NULL REFERENCES patients(id),
    visit_date TIMESTAMP NOT NULL,
    image_path TEXT NOT NULL,
    tissue_type TEXT,
    tissue_score REAL,
    inflammation TEXT,
    inflammation_score REAL,
    moisture TEXT,
    moisture_score REAL,
    edge TEXT,
    edge_score REAL,
    embedding BLOB,
    zeroshot_scores TEXT,
    audio_path TEXT,
    nurse_notes TEXT,
    text_notes TEXT,
    change_score REAL,
    trajectory TEXT,
    contradiction_flag BOOLEAN DEFAULT FALSE,
    contradiction_detail TEXT,
    report_text TEXT,
    alert_level TEXT,
    alert_detail TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""


def _db_path() -> str:
    """Derive the SQLite file path from DATABASE_URL."""
    url = settings.DATABASE_URL
    if url.startswith("sqlite:///"):
        return url.replace("sqlite:///", "")
    return "./data/woundchrono.db"


def init_db() -> None:
    """Create tables if they do not exist."""
    path = _db_path()
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    conn = sqlite3.connect(path)
    conn.executescript(_SCHEMA)
    conn.commit()
    conn.close()


def get_db() -> sqlite3.Connection:
    """Return a new connection with row_factory set to sqlite3.Row."""
    conn = sqlite3.connect(_db_path())
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def _row_to_dict(row: sqlite3.Row | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return dict(row)


# ---------------------------------------------------------------------------
# Patients
# ---------------------------------------------------------------------------

def create_patient(data: dict[str, Any]) -> dict[str, Any]:
    patient_id = str(uuid4())
    comorbidities = json.dumps(data.get("comorbidities", []))
    now = datetime.now(timezone.utc).isoformat()
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO patients (id, name, age, wound_type, wound_location, comorbidities, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                patient_id,
                data["name"],
                data.get("age"),
                data.get("wound_type"),
                data.get("wound_location"),
                comorbidities,
                now,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return get_patient(patient_id)  # type: ignore[return-value]


def get_patient(patient_id: str) -> dict[str, Any] | None:
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM patients WHERE id = ?", (patient_id,)).fetchone()
        result = _row_to_dict(row)
        if result is not None:
            result["comorbidities"] = json.loads(result.get("comorbidities") or "[]")
        return result
    finally:
        conn.close()


def list_patients() -> list[dict[str, Any]]:
    conn = get_db()
    try:
        rows = conn.execute("SELECT * FROM patients ORDER BY created_at DESC").fetchall()
        patients = []
        for row in rows:
            p = dict(row)
            p["comorbidities"] = json.loads(p.get("comorbidities") or "[]")
            patients.append(p)
        return patients
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Assessments
# ---------------------------------------------------------------------------

def create_assessment(data: dict[str, Any]) -> dict[str, Any]:
    assessment_id = str(uuid4())
    now = datetime.now(timezone.utc).isoformat()
    visit_date = data.get("visit_date") or now
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO assessments (id, patient_id, visit_date, image_path, audio_path, text_notes, created_at) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                assessment_id,
                data["patient_id"],
                visit_date,
                data["image_path"],
                data.get("audio_path"),
                data.get("text_notes"),
                now,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return get_assessment(assessment_id)  # type: ignore[return-value]


def get_assessment(assessment_id: str) -> dict[str, Any] | None:
    conn = get_db()
    try:
        row = conn.execute("SELECT * FROM assessments WHERE id = ?", (assessment_id,)).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()


def get_patient_assessments(patient_id: str) -> list[dict[str, Any]]:
    conn = get_db()
    try:
        rows = conn.execute(
            "SELECT * FROM assessments WHERE patient_id = ? ORDER BY visit_date ASC",
            (patient_id,),
        ).fetchall()
        return [dict(r) for r in rows]
    finally:
        conn.close()


def update_assessment(assessment_id: str, data: dict[str, Any]) -> dict[str, Any] | None:
    conn = get_db()
    try:
        # Build SET clause dynamically from provided keys
        allowed = {
            "tissue_type", "tissue_score", "inflammation", "inflammation_score",
            "moisture", "moisture_score", "edge", "edge_score", "embedding",
            "zeroshot_scores", "audio_path", "nurse_notes", "text_notes",
            "change_score", "trajectory", "contradiction_flag",
            "contradiction_detail", "report_text", "alert_level", "alert_detail",
        }
        cols = []
        vals: list[Any] = []
        for k, v in data.items():
            if k in allowed:
                cols.append(f"{k} = ?")
                vals.append(v)
        if not cols:
            return get_assessment(assessment_id)
        vals.append(assessment_id)
        conn.execute(
            f"UPDATE assessments SET {', '.join(cols)} WHERE id = ?",
            vals,
        )
        conn.commit()
    finally:
        conn.close()
    return get_assessment(assessment_id)


def get_latest_assessment(
    patient_id: str,
    *,
    exclude_id: str | None = None,
    before_date: str | None = None,
) -> dict[str, Any] | None:
    """Return the most recent analyzed assessment for a patient.

    If *before_date* is given, only considers assessments with visit_date < before_date.
    If *exclude_id* is given, excludes that assessment by id.
    Only returns assessments that have an embedding (i.e. have been analyzed).
    """
    conn = get_db()
    try:
        conditions = ["patient_id = ?"]
        params: list[Any] = [patient_id]

        if exclude_id:
            conditions.append("id != ?")
            params.append(exclude_id)

        if before_date:
            conditions.append("visit_date < ?")
            params.append(before_date)

        # Only consider assessments that have been analyzed (have embedding)
        conditions.append("embedding IS NOT NULL")

        where = " AND ".join(conditions)
        row = conn.execute(
            f"SELECT * FROM assessments WHERE {where} ORDER BY visit_date DESC LIMIT 1",
            params,
        ).fetchone()
        return _row_to_dict(row)
    finally:
        conn.close()
