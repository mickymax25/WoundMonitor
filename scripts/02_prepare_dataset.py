"""Unify all wound & burn datasets into a single manifest with normalized images."""

from __future__ import annotations

import csv
import hashlib
import os
import sys
from pathlib import Path

from PIL import Image
from sklearn.model_selection import train_test_split
from tqdm import tqdm

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DATA_ROOT = Path.home() / "WoundChrono" / "data"
DATASETS_DIR = DATA_ROOT / "datasets"
CO2_DIR = DATA_ROOT / "CO2Wounds-V2 Extended Chronic Wounds Dataset From Leprosy Patients"
OUTPUT_DIR = DATA_ROOT / "unified_dataset"
MANIFEST_PATH = DATA_ROOT / "manifest.csv"
MAX_SIZE = 512  # max dimension in pixels
QUALITY = 90


# ---------------------------------------------------------------------------
# Dataset-specific scanners
# ---------------------------------------------------------------------------

def scan_co2wounds() -> list[dict]:
    """CO2Wounds-V2: all images are chronic wounds from leprosy patients."""
    imgs_dir = CO2_DIR / "imgs"
    if not imgs_dir.exists():
        print(f"  [WARN] CO2Wounds not found at {imgs_dir}")
        return []
    entries = []
    for f in sorted(imgs_dir.iterdir()):
        if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".bmp"):
            entries.append({
                "source_path": str(f),
                "wound_type": "chronic_wound",
                "source_dataset": "co2wounds_v2",
            })
    return entries


def scan_dfu() -> list[dict]:
    """Diabetic Foot Ulcer dataset."""
    base = DATASETS_DIR / "diabetic-foot-ulcer-dfu"
    if not base.exists():
        print(f"  [WARN] DFU not found at {base}")
        return []
    entries = []
    for f in sorted(base.rglob("*")):
        if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".bmp"):
            entries.append({
                "source_path": str(f),
                "wound_type": "diabetic_ulcer",
                "source_dataset": "dfu",
            })
    return entries


def scan_wound_classification() -> list[dict]:
    """Wound Classification dataset — subfolders indicate type."""
    base = DATASETS_DIR / "wound-classification"
    if not base.exists():
        print(f"  [WARN] Wound Classification not found at {base}")
        return []
    type_map = {
        "abrasion": "other",
        "bruise": "other",
        "burn": "burn_2nd",
        "cut": "other",
        "diabetic": "diabetic_ulcer",
        "laceration": "other",
        "normal": None,  # skip normal skin
        "pressure": "pressure_ulcer",
        "surgical": "other",
        "venous": "venous_ulcer",
    }
    entries = []
    for subdir in sorted(base.rglob("*")):
        if not subdir.is_dir():
            continue
        folder_name = subdir.name.lower().strip()
        wtype = type_map.get(folder_name)
        if wtype is None:
            continue
        for f in sorted(subdir.iterdir()):
            if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".bmp"):
                entries.append({
                    "source_path": str(f),
                    "wound_type": wtype,
                    "source_dataset": "wound_classification",
                })
    return entries


def scan_wound_dataset() -> list[dict]:
    """Generic Wound Dataset."""
    base = DATASETS_DIR / "wound-dataset"
    if not base.exists():
        print(f"  [WARN] Wound Dataset not found at {base}")
        return []
    entries = []
    for f in sorted(base.rglob("*")):
        if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".bmp"):
            parent = f.parent.name.lower()
            if "burn" in parent:
                wtype = "burn_2nd"
            elif "diabet" in parent:
                wtype = "diabetic_ulcer"
            elif "pressure" in parent:
                wtype = "pressure_ulcer"
            elif "venous" in parent:
                wtype = "venous_ulcer"
            else:
                wtype = "chronic_wound"
            entries.append({
                "source_path": str(f),
                "wound_type": wtype,
                "source_dataset": "wound_dataset",
            })
    return entries


def scan_wound_segmentation() -> list[dict]:
    """Wound Segmentation dataset — images only (skip masks)."""
    base = DATASETS_DIR / "wound-segmentation-images"
    if not base.exists():
        print(f"  [WARN] Wound Segmentation not found at {base}")
        return []
    entries = []
    for f in sorted(base.rglob("*")):
        if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".bmp"):
            # Skip mask files
            if "mask" in f.name.lower() or "label" in f.name.lower():
                continue
            entries.append({
                "source_path": str(f),
                "wound_type": "chronic_wound",
                "source_dataset": "wound_segmentation",
            })
    return entries


def scan_skin_burn() -> list[dict]:
    """Skin Burn Dataset — subfolders by degree."""
    base = DATASETS_DIR / "skin-burn-dataset"
    if not base.exists():
        print(f"  [WARN] Skin Burn not found at {base}")
        return []
    entries = []
    for f in sorted(base.rglob("*")):
        if f.suffix.lower() in (".jpg", ".jpeg", ".png", ".bmp"):
            parent = f.parent.name.lower()
            if "first" in parent or "1st" in parent or "class_0" in parent or "class 0" in parent:
                wtype = "burn_1st"
            elif "third" in parent or "3rd" in parent or "class_2" in parent or "class 2" in parent:
                wtype = "burn_3rd"
            else:
                wtype = "burn_2nd"
            entries.append({
                "source_path": str(f),
                "wound_type": wtype,
                "source_dataset": "skin_burn",
            })
    return entries


# ---------------------------------------------------------------------------
# Normalize & copy
# ---------------------------------------------------------------------------

def normalize_image(src: str, dest: str) -> bool:
    """Resize and convert image to JPEG. Returns True on success."""
    try:
        img = Image.open(src).convert("RGB")
        w, h = img.size
        if max(w, h) > MAX_SIZE:
            ratio = MAX_SIZE / max(w, h)
            img = img.resize((int(w * ratio), int(h * ratio)), Image.LANCZOS)
        img.save(dest, "JPEG", quality=QUALITY)
        return True
    except Exception as e:
        print(f"  [ERR] {src}: {e}")
        return False


def unique_filename(source_path: str, wound_type: str) -> str:
    """Generate a unique filename based on source path hash."""
    h = hashlib.md5(source_path.encode()).hexdigest()[:10]
    return f"{wound_type}_{h}.jpg"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    print("=== Scanning datasets ===")

    scanners = [
        ("CO2Wounds-V2", scan_co2wounds),
        ("DFU", scan_dfu),
        ("Wound Classification", scan_wound_classification),
        ("Wound Dataset", scan_wound_dataset),
        ("Wound Segmentation", scan_wound_segmentation),
        ("Skin Burn", scan_skin_burn),
    ]

    all_entries: list[dict] = []
    for name, scanner in scanners:
        entries = scanner()
        print(f"  {name}: {len(entries)} images")
        all_entries.extend(entries)

    print(f"\nTotal: {len(all_entries)} images")

    # Normalize and copy
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []

    print("\n=== Normalizing images ===")
    for entry in tqdm(all_entries, desc="Processing"):
        fname = unique_filename(entry["source_path"], entry["wound_type"])
        dest = OUTPUT_DIR / fname
        if dest.exists() or normalize_image(entry["source_path"], str(dest)):
            rows.append({
                "image_path": str(dest),
                "image_filename": fname,
                "wound_type": entry["wound_type"],
                "source_dataset": entry["source_dataset"],
            })

    print(f"\nSuccessfully processed: {len(rows)} images")

    # Train/val split (stratified by wound_type)
    types = [r["wound_type"] for r in rows]
    indices = list(range(len(rows)))
    train_idx, val_idx = train_test_split(
        indices, test_size=0.15, stratify=types, random_state=42
    )
    for i in train_idx:
        rows[i]["split"] = "train"
    for i in val_idx:
        rows[i]["split"] = "val"

    # Write manifest
    with open(MANIFEST_PATH, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["image_path", "image_filename", "wound_type", "source_dataset", "split"])
        writer.writeheader()
        writer.writerows(rows)

    print(f"\nManifest written to {MANIFEST_PATH}")

    # Summary
    from collections import Counter
    type_counts = Counter(r["wound_type"] for r in rows)
    split_counts = Counter(r["split"] for r in rows)
    print("\n=== Summary ===")
    for t, c in sorted(type_counts.items()):
        print(f"  {t}: {c}")
    print(f"\n  Train: {split_counts['train']}, Val: {split_counts['val']}")


if __name__ == "__main__":
    main()
