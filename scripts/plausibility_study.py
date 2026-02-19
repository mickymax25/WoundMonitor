"""Plausibility study: run pipeline on 30 assessments via API, store in DB.

- 10 patients x 2 visits (trajectory + contradiction testing)
- 10 patients x 1 visit (single assessment plausibility)
- Total: 30 analyses

For 2-visit patients, visit 2 includes nurse text_notes:
  - 5 patients: contradictory notes ("wound looks much better" on potentially worsening wounds)
  - 5 patients: coherent notes ("wound appears to be worsening" or "stable, no change")

Results are stored in DB and visible in the frontend.
"""

from __future__ import annotations

import csv
import json
import random
import sys
import time
from pathlib import Path

import requests

API_BASE = "http://localhost:8000/api/v1"
MANIFEST = Path.home() / "WoundChrono" / "data" / "manifest.csv"
RESULTS_FILE = Path.home() / "WoundChrono" / "plausibility_results.json"

# Nurse notes for contradiction testing
CONTRADICTORY_NOTES = [
    "The wound looks much better this week, patient reports less pain.",
    "Significant improvement noted, wound bed appears cleaner.",
    "Wound is healing nicely, granulation tissue visible throughout.",
    "Patient says wound feels better, less drainage observed.",
    "Good progress, wound edges are contracting well.",
]

COHERENT_WORSENING_NOTES = [
    "Wound appears to be getting worse, increased exudate noted.",
    "Patient reports more pain, perilesional skin looks inflamed.",
    "No improvement since last visit, possible early infection signs.",
    "Wound bed looks more necrotic, odor present.",
    "Deterioration noted, wound edges are undermined.",
]

# Patient name templates
FIRST_NAMES = ["Maria", "James", "Rosa", "David", "Sarah", "Carlos", "Emma", "Robert", "Ana", "John",
               "Linda", "Ahmed", "Fatima", "Wei", "Priya", "Thomas", "Elena", "Omar", "Yuki", "Patrick"]
LAST_NAMES = ["Garcia", "Smith", "Johnson", "Rodriguez", "Williams", "Chen", "Kumar", "Patel", "Kim", "Martinez",
              "Brown", "Wilson", "Taylor", "Anderson", "Thomas", "Lee", "Harris", "Clark", "Lewis", "Robinson"]


def load_manifest() -> list[dict]:
    """Load and parse the manifest CSV."""
    rows = []
    with open(MANIFEST) as f:
        reader = csv.DictReader(f)
        for row in reader:
            rows.append(row)
    return rows


def select_images(manifest: list[dict]) -> dict:
    """Select images for the study.

    Returns dict with:
      - 'temporal_pairs': list of 10 pairs [(img1, img2), ...] for 2-visit patients
      - 'singles': list of 10 images for 1-visit patients
    """
    random.seed(42)

    # Group by wound type
    by_type = {}
    for row in manifest:
        wtype = row["wound_type"]
        if wtype not in by_type:
            by_type[wtype] = []
        by_type[wtype].append(row)

    # For temporal pairs: pick pairs from same wound type (simulating same patient over time)
    # Mix of chronic wounds, diabetic ulcers, and burns
    temporal_pairs = []

    # 4 chronic wound pairs
    chronic = by_type.get("chronic_wound", [])
    random.shuffle(chronic)
    for i in range(0, 8, 2):
        temporal_pairs.append((chronic[i], chronic[i + 1]))

    # 3 diabetic ulcer pairs
    diabetic = by_type.get("diabetic_ulcer", [])
    random.shuffle(diabetic)
    for i in range(0, 6, 2):
        temporal_pairs.append((diabetic[i], diabetic[i + 1]))

    # 3 burn pairs (tests burn-specific pipeline path)
    burns = by_type.get("burn_2nd", [])
    random.shuffle(burns)
    for i in range(0, 6, 2):
        temporal_pairs.append((burns[i], burns[i + 1]))

    # For singles: diverse mix including burns
    used_paths = set()
    for p1, p2 in temporal_pairs:
        used_paths.add(p1["image_path"])
        used_paths.add(p2["image_path"])

    singles = []
    type_quotas = {"chronic_wound": 3, "diabetic_ulcer": 3, "burn_2nd": 3, "other": 1}
    for wtype, count in type_quotas.items():
        pool = [r for r in by_type.get(wtype, []) if r["image_path"] not in used_paths]
        random.shuffle(pool)
        singles.extend(pool[:count])

    return {"temporal_pairs": temporal_pairs, "singles": singles}


def create_patient(name: str, wound_type: str, comorbidities: list[str] | None = None) -> dict:
    """Create a patient via API."""
    resp = requests.post(f"{API_BASE}/patients", json={
        "name": name,
        "wound_type": wound_type,
        "comorbidities": comorbidities or [],
    })
    resp.raise_for_status()
    return resp.json()


def create_assessment(patient_id: str, image_path: str, text_notes: str | None = None) -> dict:
    """Create an assessment via API (upload image)."""
    with open(image_path, "rb") as f:
        files = {"image": (Path(image_path).name, f, "image/jpeg")}
        data = {"patient_id": patient_id}
        if text_notes:
            data["text_notes"] = text_notes
        resp = requests.post(f"{API_BASE}/assessments", data=data, files=files)
    resp.raise_for_status()
    return resp.json()


def analyze_assessment(assessment_id: str) -> dict:
    """Run AI analysis on an assessment."""
    resp = requests.post(f"{API_BASE}/assessments/{assessment_id}/analyze", timeout=300)
    resp.raise_for_status()
    return resp.json()


def extract_scores(result: dict) -> dict[str, float]:
    """Extract TIME scores from AnalysisResult."""
    tc = result.get("time_classification", {})
    return {
        "tissue": tc.get("tissue", {}).get("score", 0),
        "inflammation": tc.get("inflammation", {}).get("score", 0),
        "moisture": tc.get("moisture", {}).get("score", 0),
        "edge": tc.get("edge", {}).get("score", 0),
    }


def extract_descriptions(result: dict) -> dict[str, str]:
    """Extract TIME descriptions from AnalysisResult."""
    tc = result.get("time_classification", {})
    return {
        "tissue": tc.get("tissue", {}).get("type", "?"),
        "inflammation": tc.get("inflammation", {}).get("type", "?"),
        "moisture": tc.get("moisture", {}).get("type", "?"),
        "edge": tc.get("edge", {}).get("type", "?"),
    }


def print_result(result: dict, elapsed: float):
    """Print a single analysis result."""
    s = extract_scores(result)
    d = extract_descriptions(result)
    print(f"    TIME: T={s['tissue']:.2f} ({d['tissue']}) "
          f"I={s['inflammation']:.2f} M={s['moisture']:.2f} E={s['edge']:.2f}")
    print(f"    Trajectory: {result.get('trajectory', '?')} "
          f"| Alert: {result.get('alert_level', '?')} | {elapsed:.0f}s")


def run_study():
    """Run the full plausibility study."""
    print("=" * 60)
    print("WOUND MONITOR — PLAUSIBILITY STUDY (N=30)")
    print("=" * 60)

    # Load manifest and select images
    manifest = load_manifest()
    print(f"Loaded manifest: {len(manifest)} images")

    selection = select_images(manifest)
    print(f"Selected: {len(selection['temporal_pairs'])} temporal pairs + {len(selection['singles'])} singles")
    print()

    results = {
        "temporal_patients": [],
        "single_patients": [],
        "summary": {},
    }

    total_analyses = len(selection["temporal_pairs"]) * 2 + len(selection["singles"])
    analysis_count = 0
    start_time = time.time()

    # --- Phase 1: Temporal pair patients (2 visits each) ---
    print("-" * 60)
    print("PHASE 1: Temporal pair patients (10 patients x 2 visits)")
    print("-" * 60)

    for i, (img1, img2) in enumerate(selection["temporal_pairs"]):
        patient_name = f"{FIRST_NAMES[i]} {LAST_NAMES[i]}"
        wound_type = img1["wound_type"]

        # Determine nurse notes for visit 2
        if i < 5:
            # Contradictory: say "looks better" regardless of AI assessment
            notes = CONTRADICTORY_NOTES[i]
            notes_type = "contradictory"
        else:
            # Coherent worsening notes
            notes = COHERENT_WORSENING_NOTES[i - 5]
            notes_type = "coherent_worsening"

        comorbidities = random.choice([
            ["Type 2 diabetes", "Hypertension"],
            ["Peripheral vascular disease"],
            ["Diabetes mellitus", "Obesity"],
            ["Venous insufficiency"],
            ["Neuropathy", "Chronic kidney disease"],
        ])

        print(f"\n[Patient {i+1}/10] {patient_name} ({wound_type})")

        # Create patient
        patient = create_patient(patient_name, wound_type, comorbidities)
        patient_id = patient["id"]
        print(f"  Created patient: {patient_id}")

        patient_result = {
            "patient_id": patient_id,
            "patient_name": patient_name,
            "wound_type": wound_type,
            "notes_type": notes_type,
            "visits": [],
        }

        # Visit 1 (no notes)
        analysis_count += 1
        print(f"  Visit 1 [{analysis_count}/{total_analyses}]: {Path(img1['image_path']).name}")
        t0 = time.time()
        assessment1 = create_assessment(patient_id, img1["image_path"])
        result1 = analyze_assessment(assessment1["id"])
        elapsed1 = time.time() - t0
        print_result(result1, elapsed1)
        patient_result["visits"].append({
            "visit": 1,
            "image": img1["image_path"],
            "result": result1,
            "elapsed_s": round(elapsed1, 1),
        })

        # Visit 2 (with nurse notes)
        analysis_count += 1
        print(f"  Visit 2 [{analysis_count}/{total_analyses}]: {Path(img2['image_path']).name}")
        print(f"    Nurse notes ({notes_type}): \"{notes[:60]}...\"")
        t0 = time.time()
        assessment2 = create_assessment(patient_id, img2["image_path"], text_notes=notes)
        result2 = analyze_assessment(assessment2["id"])
        elapsed2 = time.time() - t0
        print_result(result2, elapsed2)
        print(f"    Contradiction: {result2.get('contradiction_flag', False)}"
              f" — {result2.get('contradiction_detail', 'N/A')}")
        patient_result["visits"].append({
            "visit": 2,
            "image": img2["image_path"],
            "text_notes": notes,
            "notes_type": notes_type,
            "result": result2,
            "elapsed_s": round(elapsed2, 1),
        })

        results["temporal_patients"].append(patient_result)

    # --- Phase 2: Single visit patients ---
    print("\n" + "-" * 60)
    print("PHASE 2: Single visit patients (10 patients x 1 visit)")
    print("-" * 60)

    for i, img in enumerate(selection["singles"]):
        idx = 10 + i
        patient_name = f"{FIRST_NAMES[idx]} {LAST_NAMES[idx]}"
        wound_type = img["wound_type"]

        print(f"\n[Patient {i+1}/10] {patient_name} ({wound_type})")

        patient = create_patient(patient_name, wound_type)
        patient_id = patient["id"]

        analysis_count += 1
        print(f"  Visit 1 [{analysis_count}/{total_analyses}]: {Path(img['image_path']).name}")
        t0 = time.time()
        assessment = create_assessment(patient_id, img["image_path"])
        result = analyze_assessment(assessment["id"])
        elapsed = time.time() - t0
        print_result(result, elapsed)

        results["single_patients"].append({
            "patient_id": patient_id,
            "patient_name": patient_name,
            "wound_type": wound_type,
            "result": result,
            "elapsed_s": round(elapsed, 1),
        })

    # --- Summary ---
    total_time = time.time() - start_time

    # Compute aggregate stats
    all_scores = []
    all_latencies = []
    contradictions_detected = 0
    contradictions_expected = 0

    for p in results["temporal_patients"]:
        for v in p["visits"]:
            scores = extract_scores(v["result"])
            all_scores.append(scores)
            all_latencies.append(v["elapsed_s"])
            if v.get("notes_type") == "contradictory":
                contradictions_expected += 1
                if v["result"].get("contradiction_flag", False):
                    contradictions_detected += 1

    for p in results["single_patients"]:
        scores = extract_scores(p["result"])
        all_scores.append(scores)
        all_latencies.append(p["elapsed_s"])

    # Score distributions
    tissue_scores = [s["tissue"] for s in all_scores]
    inflammation_scores = [s["inflammation"] for s in all_scores]
    moisture_scores = [s["moisture"] for s in all_scores]
    edge_scores = [s["edge"] for s in all_scores]

    summary = {
        "total_analyses": analysis_count,
        "total_time_min": round(total_time / 60, 1),
        "avg_latency_s": round(sum(all_latencies) / len(all_latencies), 1) if all_latencies else 0,
        "score_distributions": {
            "tissue": {"min": round(min(tissue_scores), 3), "max": round(max(tissue_scores), 3),
                      "mean": round(sum(tissue_scores)/len(tissue_scores), 3)},
            "inflammation": {"min": round(min(inflammation_scores), 3), "max": round(max(inflammation_scores), 3),
                           "mean": round(sum(inflammation_scores)/len(inflammation_scores), 3)},
            "moisture": {"min": round(min(moisture_scores), 3), "max": round(max(moisture_scores), 3),
                        "mean": round(sum(moisture_scores)/len(moisture_scores), 3)},
            "edge": {"min": round(min(edge_scores), 3), "max": round(max(edge_scores), 3),
                    "mean": round(sum(edge_scores)/len(edge_scores), 3)},
        },
        "contradiction_detection": {
            "expected": contradictions_expected,
            "detected": contradictions_detected,
            "rate": round(contradictions_detected / contradictions_expected, 2) if contradictions_expected > 0 else 0,
        },
    }
    results["summary"] = summary

    # Save results
    with open(RESULTS_FILE, "w") as f:
        json.dump(results, f, indent=2, default=str)

    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"Total analyses: {analysis_count}")
    print(f"Total time: {summary['total_time_min']} min")
    print(f"Avg latency: {summary['avg_latency_s']}s per analysis")
    print(f"\nTIME Score Distributions (N={len(all_scores)}):")
    for dim in ["tissue", "inflammation", "moisture", "edge"]:
        d = summary["score_distributions"][dim]
        print(f"  {dim:15s}: min={d['min']:.3f}  mean={d['mean']:.3f}  max={d['max']:.3f}")
    print(f"\nContradiction Detection:")
    print(f"  Expected contradictions: {summary['contradiction_detection']['expected']}")
    print(f"  Detected: {summary['contradiction_detection']['detected']}")
    print(f"  Detection rate: {summary['contradiction_detection']['rate']:.0%}")
    print(f"\nResults saved to: {RESULTS_FILE}")
    print("All assessments stored in DB — visible in frontend.")


if __name__ == "__main__":
    run_study()
