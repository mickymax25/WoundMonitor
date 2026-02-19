"""Test the two fixes: all-zero fallback + rule-based contradiction."""

import time
import requests

API = "http://localhost:8000/api/v1"
DATA = "/home/michaelsiam/WoundChrono/data/unified_dataset"


def test_allzero_fallback():
    """Test 1: Image that previously gave all-zero scores."""
    print("=== TEST 1: All-zero fallback ===")

    # This image gave T=0 I=0 M=0 E=0 in the plausibility study
    img_path = f"{DATA}/chronic_wound_fccccfe70e.jpg"

    p = requests.post(f"{API}/patients", json={
        "name": "Fix Test 1", "wound_type": "chronic_wound", "comorbidities": [],
    }).json()
    pid = p["id"]

    with open(img_path, "rb") as f:
        a = requests.post(
            f"{API}/assessments",
            data={"patient_id": pid},
            files={"image": ("test.jpg", f, "image/jpeg")},
        ).json()
    aid = a["id"]

    t0 = time.time()
    r = requests.post(f"{API}/assessments/{aid}/analyze", timeout=300).json()
    elapsed = time.time() - t0

    tc = r.get("time_classification", {})
    all_zero = all(tc.get(d, {}).get("score", 0) == 0.0 for d in ("tissue", "inflammation", "moisture", "edge"))

    for dim in ["tissue", "inflammation", "moisture", "edge"]:
        s = tc.get(dim, {})
        print(f"  {dim}: score={s.get('score', '?')} type={s.get('type', '?')}")
    print(f"  Trajectory: {r.get('trajectory')} | Alert: {r.get('alert_level')} | {elapsed:.1f}s")
    print(f"  All-zero: {all_zero} (should be False if fallback works)")
    print()


def test_contradiction():
    """Test 2: Rule-based contradiction detection."""
    print("=== TEST 2: Rule-based contradiction ===")

    # Visit 1: image with valid scores
    img1 = f"{DATA}/chronic_wound_331a8be70c.jpg"
    # Visit 2: different image + contradictory nurse notes
    img2 = f"{DATA}/chronic_wound_d871c8766a.jpg"

    p = requests.post(f"{API}/patients", json={
        "name": "Fix Test 2", "wound_type": "chronic_wound", "comorbidities": [],
    }).json()
    pid = p["id"]

    # Visit 1 (no notes)
    with open(img1, "rb") as f:
        a1 = requests.post(
            f"{API}/assessments",
            data={"patient_id": pid},
            files={"image": ("v1.jpg", f, "image/jpeg")},
        ).json()

    r1 = requests.post(f"{API}/assessments/{a1['id']}/analyze", timeout=300).json()
    tc1 = r1.get("time_classification", {})
    print(f"  Visit 1: T={tc1.get('tissue', {}).get('score', '?')} "
          f"I={tc1.get('inflammation', {}).get('score', '?')} "
          f"Alert={r1.get('alert_level')}")

    # Visit 2 (contradictory notes: says "better" regardless of AI)
    with open(img2, "rb") as f:
        a2 = requests.post(
            f"{API}/assessments",
            data={
                "patient_id": pid,
                "text_notes": "The wound looks much better this week, healing nicely.",
            },
            files={"image": ("v2.jpg", f, "image/jpeg")},
        ).json()

    t0 = time.time()
    r2 = requests.post(f"{API}/assessments/{a2['id']}/analyze", timeout=300).json()
    elapsed = time.time() - t0

    tc2 = r2.get("time_classification", {})
    print(f"  Visit 2: T={tc2.get('tissue', {}).get('score', '?')} "
          f"I={tc2.get('inflammation', {}).get('score', '?')}")
    print(f"  Trajectory: {r2.get('trajectory')} | Alert: {r2.get('alert_level')}")
    print(f"  Contradiction: {r2.get('contradiction_flag')} — {r2.get('contradiction_detail')}")
    print(f"  Latency: {elapsed:.1f}s")
    print()

    if r2.get("trajectory") == "deteriorating":
        expected = True
        print(f"  Expected contradiction=True (nurse says better, AI says deteriorating): "
              f"{'PASS' if r2.get('contradiction_flag') else 'FAIL'}")
    else:
        print(f"  Trajectory is '{r2.get('trajectory')}', not deteriorating — "
              f"contradiction test inconclusive for this image pair.")


if __name__ == "__main__":
    test_allzero_fallback()
    test_contradiction()
