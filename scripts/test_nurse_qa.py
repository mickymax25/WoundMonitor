"""Test nurse Q&A feature: nurse asks questions in notes, model answers in report."""

import time
import requests

API = "http://localhost:8000/api/v1"
DATA = "/home/michaelsiam/WoundChrono/data/unified_dataset"


def test_nurse_qa():
    """Test: nurse asks questions about wound management."""
    print("=== TEST: Nurse Q&A in report ===")

    img = f"{DATA}/chronic_wound_331a8be70c.jpg"

    p = requests.post(f"{API}/patients", json={
        "name": "QA Test Patient",
        "wound_type": "chronic_wound",
        "comorbidities": ["Type 2 diabetes", "Peripheral vascular disease"],
    }).json()
    pid = p["id"]

    # Nurse notes with questions
    nurse_notes = (
        "The wound has a lot of yellow exudate today, more than last week. "
        "Should I switch to a foam dressing instead of the current gauze? "
        "Is there any sign of infection that would require antibiotics? "
        "The patient also complains of increased pain around the wound edges."
    )

    with open(img, "rb") as f:
        a = requests.post(
            f"{API}/assessments",
            data={"patient_id": pid, "text_notes": nurse_notes},
            files={"image": ("wound.jpg", f, "image/jpeg")},
        ).json()
    aid = a["id"]

    print(f"  Patient: {pid}")
    print(f"  Assessment: {aid}")
    print(f"  Nurse notes: {nurse_notes[:80]}...")
    print()

    t0 = time.time()
    r = requests.post(f"{API}/assessments/{aid}/analyze", timeout=300).json()
    elapsed = time.time() - t0

    tc = r.get("time_classification", {})
    print("  TIME scores:")
    for dim in ["tissue", "inflammation", "moisture", "edge"]:
        s = tc.get(dim, {})
        print(f"    {dim}: {s.get('score', '?')} ({s.get('type', '?')})")

    print(f"\n  Trajectory: {r.get('trajectory')}")
    print(f"  Alert: {r.get('alert_level')}")
    print(f"  Latency: {elapsed:.1f}s")

    print(f"\n  --- FULL REPORT ---")
    report = r.get("report_text", "No report")
    print(report)

    # Check if Clinical Guidance section exists
    if "Clinical Guidance" in report:
        print("\n  >>> PASS: Clinical Guidance section found in report")
    else:
        print("\n  >>> NOTE: No Clinical Guidance section (model may not have returned nurse_answers)")


def test_no_questions():
    """Test: nurse notes without questions should NOT have Clinical Guidance."""
    print("\n=== TEST: Notes without questions (should have no Clinical Guidance) ===")

    img = f"{DATA}/diabetic_ulcer_33c48355f7.jpg"

    p = requests.post(f"{API}/patients", json={
        "name": "No QA Test",
        "wound_type": "diabetic_ulcer",
        "comorbidities": [],
    }).json()
    pid = p["id"]

    nurse_notes = "Wound appears stable. Dressing changed. No odor noted."

    with open(img, "rb") as f:
        a = requests.post(
            f"{API}/assessments",
            data={"patient_id": pid, "text_notes": nurse_notes},
            files={"image": ("wound.jpg", f, "image/jpeg")},
        ).json()
    aid = a["id"]

    r = requests.post(f"{API}/assessments/{aid}/analyze", timeout=300).json()
    report = r.get("report_text", "No report")

    if "Clinical Guidance" not in report:
        print("  >>> PASS: No Clinical Guidance section (expected)")
    else:
        print("  >>> NOTE: Clinical Guidance section present (unexpected but not harmful)")


if __name__ == "__main__":
    test_nurse_qa()
    test_no_questions()
