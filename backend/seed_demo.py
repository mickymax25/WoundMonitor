"""Seed script — populates the database with 3 demo patients and their wound images.

Uses images from CO2Wounds-V2 dataset to simulate temporal wound series.
Run from the backend directory:
    python seed_demo.py
"""

from __future__ import annotations

import os
import shutil
import sys

# Ensure app is importable
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault("WOUNDCHRONO_MOCK_MODELS", "true")

from app.config import settings
from app.db import init_db, create_patient, create_assessment

DATASET_DIR = os.path.join(
    os.path.dirname(__file__),
    "..",
    "data",
    "CO2Wounds-V2 Extended Chronic Wounds Dataset From Leprosy Patients",
    "imgs",
)

# 3 demo patients with curated image sequences
DEMO_PATIENTS = [
    {
        "name": "Maria G.",
        "age": 62,
        "sex": "female",
        "phone": "+1 (555) 234-8901",
        "wound_type": "venous_ulcer",
        "wound_location": "left_leg",
        "comorbidities": ["diabetes", "hypertension", "venous_insufficiency"],
        "referring_physician": "Dr. James Chen",
        "referring_physician_specialty": "Vascular Surgery",
        "referring_physician_facility": "St. Mary's Medical Center",
        "referring_physician_phone": "+1 (555) 901-2345",
        "referring_physician_email": "j.chen@stmarys.med",
        "referring_physician_preferred_contact": "email",
        "visits": [
            {"image": "IMG435.jpg", "date": "2026-01-06T09:00:00+00:00"},
            {"image": "IMG436.jpg", "date": "2026-01-13T09:00:00+00:00"},
            {"image": "IMG437.jpg", "date": "2026-01-20T09:00:00+00:00"},
            {"image": "IMG438.jpg", "date": "2026-01-27T09:00:00+00:00"},
        ],
    },
    {
        "name": "Carlos R.",
        "age": 71,
        "sex": "male",
        "phone": "+1 (555) 876-5432",
        "wound_type": "diabetic_ulcer",
        "wound_location": "left_foot",
        "comorbidities": ["diabetes", "peripheral_neuropathy", "obesity"],
        "referring_physician": "Dr. Elena Rodriguez",
        "referring_physician_specialty": "Wound Care / Dermatology",
        "referring_physician_facility": "St. Mary's Medical Center",
        "referring_physician_phone": "+1 (555) 678-4321",
        "referring_physician_email": "e.rodriguez@stmarys.med",
        "referring_physician_preferred_contact": "phone",
        "visits": [
            {"image": "IMG473.jpg", "date": "2026-01-08T10:00:00+00:00"},
            {"image": "IMG476.jpg", "date": "2026-01-15T10:00:00+00:00"},
            {"image": "IMG480.jpg", "date": "2026-01-22T10:00:00+00:00"},
        ],
    },
    {
        "name": "Rosa T.",
        "age": 55,
        "sex": "female",
        "phone": "+1 (555) 345-6789",
        "wound_type": "pressure_ulcer",
        "wound_location": "right_leg",
        "comorbidities": ["leprosy", "anemia", "malnutrition"],
        "referring_physician": "Dr. James Chen",
        "referring_physician_specialty": "Vascular Surgery",
        "referring_physician_facility": "St. Mary's Medical Center",
        "referring_physician_phone": "+1 (555) 901-2345",
        "referring_physician_email": "j.chen@stmarys.med",
        "referring_physician_preferred_contact": "whatsapp",
        "visits": [
            {"image": "IMG583.jpg", "date": "2026-01-10T08:30:00+00:00"},
            {"image": "IMG585.jpg", "date": "2026-01-17T08:30:00+00:00"},
            {"image": "IMG539.jpg", "date": "2026-01-24T08:30:00+00:00"},
            {"image": "IMG545.jpg", "date": "2026-01-31T08:30:00+00:00"},
        ],
    },
    {
        "name": "Ahmed K.",
        "age": 34,
        "sex": "male",
        "phone": "+1 (555) 012-3456",
        "wound_type": "thermal_burn",
        "wound_location": "arm",
        "comorbidities": [],
        "referring_physician": "Dr. Sarah Patel",
        "referring_physician_specialty": "Plastic Surgery",
        "referring_physician_facility": "St. Mary's Burn Unit",
        "referring_physician_phone": "+1 (555) 234-5678",
        "referring_physician_email": "s.patel@stmarys.med",
        "referring_physician_preferred_contact": "email",
        "visits": [
            {"image": "IMG435.jpg", "date": "2026-01-12T11:00:00+00:00"},
            {"image": "IMG436.jpg", "date": "2026-01-19T11:00:00+00:00"},
            {"image": "IMG437.jpg", "date": "2026-01-26T11:00:00+00:00"},
        ],
    },
]


def main() -> None:
    init_db()
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)

    for patient_data in DEMO_PATIENTS:
        print(f"Creating patient: {patient_data['name']}")
        patient = create_patient(
            {
                "name": patient_data["name"],
                "age": patient_data["age"],
                "sex": patient_data.get("sex"),
                "phone": patient_data.get("phone"),
                "wound_type": patient_data["wound_type"],
                "wound_location": patient_data["wound_location"],
                "comorbidities": patient_data["comorbidities"],
                "referring_physician": patient_data.get("referring_physician"),
                "referring_physician_specialty": patient_data.get("referring_physician_specialty"),
                "referring_physician_facility": patient_data.get("referring_physician_facility"),
                "referring_physician_phone": patient_data.get("referring_physician_phone"),
                "referring_physician_email": patient_data.get("referring_physician_email"),
                "referring_physician_preferred_contact": patient_data.get("referring_physician_preferred_contact"),
            }
        )
        patient_id = patient["id"]

        for i, visit in enumerate(patient_data["visits"]):
            src = os.path.join(DATASET_DIR, visit["image"])
            if not os.path.isfile(src):
                print(f"  WARNING: {visit['image']} not found, skipping")
                continue

            # Copy image to uploads
            dest_dir = os.path.join(settings.UPLOAD_DIR, "patients", patient_id, "images")
            os.makedirs(dest_dir, exist_ok=True)
            dest = os.path.join(dest_dir, f"visit_{i+1}_{visit['image']}")
            shutil.copy2(src, dest)

            assessment = create_assessment(
                {
                    "patient_id": patient_id,
                    "image_path": dest,
                    "visit_date": visit["date"],
                }
            )
            print(f"  Visit {i+1}: {visit['image']} -> {assessment['id'][:8]}...")

    print("\nDone. 4 patients seeded with wound image series.")
    print("Start the backend and run analysis on each assessment.")


if __name__ == "__main__":
    main()
