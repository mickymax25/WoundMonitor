"""Generate TIME annotations for wound images using base MedGemma.

Strategy:
- Batch inference (correct nested image format)
- Prompt A first, fallback to Prompt B on refusals (single inference)
- All images processed (resume support)
- Pre-resize + reduced max_new_tokens
"""

from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

import torch
from PIL import Image
from tqdm import tqdm
from transformers import AutoProcessor, AutoModelForImageTextToText

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DATA_ROOT = Path.home() / "WoundChrono" / "data"
MANIFEST_PATH = DATA_ROOT / "manifest.csv"
OUTPUT_PATH = DATA_ROOT / "annotations_time.jsonl"
SKIP_LOG_PATH = DATA_ROOT / "annotations_skipped.log"
MODEL_ID = "google/medgemma-1.5-4b-it"
MAX_NEW_TOKENS = 150
IMAGE_MAX_SIZE = 512
BATCH_SIZE = 8  # images per batch

# ---------------------------------------------------------------------------
# Prompts
# ---------------------------------------------------------------------------

PROMPT_A = """\
Describe this wound image using the TIME wound assessment framework.
For each dimension (Tissue, Inflammation, Moisture, Edge), describe what you observe and assign a score from 0.0 (worst) to 1.0 (best/healed).
Return your assessment as a JSON object."""

PROMPT_A_BURN = """\
Describe this burn wound image using the TIME wound assessment framework.
For each dimension (Tissue, Inflammation, Moisture, Edge), describe what you observe and assign a score from 0.0 (worst) to 1.0 (best/healed).
Return your assessment as a JSON object."""

PROMPT_B = """\
Assess this wound photograph. Score each TIME dimension from 0.0 to 1.0.
T=Tissue quality, I=Inflammation level, M=Moisture balance, E=Edge advancement.
Output JSON with keys: tissue, inflammation, moisture, edge. Each has type (string) and score (float)."""

PROMPT_B_BURN = """\
Assess this burn wound photograph. Score each TIME dimension from 0.0 to 1.0.
T=Tissue quality, I=Inflammation level, M=Moisture balance, E=Edge advancement.
Output JSON with keys: tissue, inflammation, moisture, edge. Each has type (string) and score (float)."""

SYSTEM_MSG = "You are a medical imaging AI that analyzes wound photographs for clinical documentation."

REFUSAL_KEYWORDS = [
    "i am unable to", "i cannot provide", "i'm unable to",
    "cannot provide medical", "consult a healthcare",
    "seek medical advice", "i can't provide", "cannot diagnose",
]


def is_burn(wound_type: str) -> bool:
    return "burn" in wound_type.lower()


def is_refusal(text: str) -> bool:
    lower = text.lower()
    return any(kw in lower for kw in REFUSAL_KEYWORDS)


# ---------------------------------------------------------------------------
# Model
# ---------------------------------------------------------------------------

def load_model():
    print(f"Loading {MODEL_ID}...")
    # padding_side="left" is required for batched generation
    processor = AutoProcessor.from_pretrained(
        MODEL_ID, trust_remote_code=True, padding_side="left"
    )
    model = AutoModelForImageTextToText.from_pretrained(
        MODEL_ID,
        torch_dtype=torch.bfloat16,
        device_map="auto",
        trust_remote_code=True,
    )
    model.eval()
    print(f"Model loaded on {model.device}")
    return model, processor


def load_image(path: str) -> Image.Image | None:
    try:
        img = Image.open(path).convert("RGB")
        w, h = img.size
        if max(w, h) > IMAGE_MAX_SIZE:
            scale = IMAGE_MAX_SIZE / max(w, h)
            img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)
        return img
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Batch inference
# ---------------------------------------------------------------------------

def generate_batch(model, processor, images: list[Image.Image],
                   prompts: list[str]) -> list[str]:
    """Batched inference — process multiple images in one forward pass."""
    # Build conversations
    conversations = []
    for img, prompt in zip(images, prompts):
        msgs = [
            {
                "role": "user",
                "content": [
                    {"type": "image", "image": img},
                    {"type": "text", "text": prompt},
                ],
            }
        ]
        conversations.append(msgs)

    # Apply chat template per conversation
    texts = [
        processor.apply_chat_template(conv, add_generation_prompt=True)
        for conv in conversations
    ]

    # KEY FIX: images must be nested list [[img1], [img2], ...] not flat [img1, img2, ...]
    nested_images = [[img] for img in images]

    inputs = processor(
        text=texts,
        images=nested_images,
        return_tensors="pt",
        padding=True,
        truncation=True,
    ).to(model.device)

    with torch.no_grad():
        output_ids = model.generate(
            **inputs,
            max_new_tokens=MAX_NEW_TOKENS,
            do_sample=False,
        )

    # Decode each sample — skip input tokens (padded to same length)
    input_len = inputs["input_ids"].shape[1]
    results = []
    for i in range(len(images)):
        generated = output_ids[i][input_len:]
        text = processor.decode(generated, skip_special_tokens=True).strip()
        results.append(text)

    return results


def generate_single(model, processor, image: Image.Image, prompt: str,
                    use_system: bool = False) -> str:
    """Single inference — used for Prompt B fallback with system message."""
    if use_system:
        messages = [
            {"role": "system", "content": [{"type": "text", "text": SYSTEM_MSG}]},
            {"role": "user", "content": [
                {"type": "image", "image": image},
                {"type": "text", "text": prompt},
            ]},
        ]
    else:
        messages = [
            {"role": "user", "content": [
                {"type": "image", "image": image},
                {"type": "text", "text": prompt},
            ]},
        ]

    input_text = processor.apply_chat_template(messages, add_generation_prompt=True)
    inputs = processor(
        text=input_text, images=[[image]], return_tensors="pt",
    ).to(model.device)

    with torch.no_grad():
        output_ids = model.generate(
            **inputs, max_new_tokens=MAX_NEW_TOKENS, do_sample=False,
        )

    generated = output_ids[0][inputs["input_ids"].shape[1]:]
    return processor.decode(generated, skip_special_tokens=True).strip()


# ---------------------------------------------------------------------------
# JSON parsing and normalization
# ---------------------------------------------------------------------------

def parse_json_response(text: str) -> dict | None:
    cleaned = re.sub(r'```(?:json)?\s*', '', text).strip()
    cleaned = cleaned.rstrip('`').strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        pass
    match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', cleaned, re.DOTALL)
    if match:
        try:
            return json.loads(match.group())
        except json.JSONDecodeError:
            pass
    return None


def normalize_time_scores(raw: dict) -> dict | None:
    dims = ["tissue", "inflammation", "moisture", "edge"]
    normalized = {}
    for dim in dims:
        val = raw.get(dim) or raw.get(dim.capitalize()) or raw.get(dim.upper())
        if val is None:
            for k, v in raw.items():
                if k.lower().startswith(dim[:4]):
                    val = v
                    break
        if val is None:
            return None
        if isinstance(val, dict):
            score = val.get("score")
            desc = val.get("type", val.get("description", "observed"))
            if score is None:
                return None
            try:
                score = float(score)
            except (TypeError, ValueError):
                return None
            normalized[dim] = {"type": str(desc), "score": score}
        elif isinstance(val, (int, float)):
            normalized[dim] = {"type": "observed", "score": float(val)}
        elif isinstance(val, str):
            try:
                normalized[dim] = {"type": "observed", "score": float(val)}
            except ValueError:
                return None
        else:
            return None
    for dim in dims:
        s = normalized[dim]["score"]
        if not (0.0 <= s <= 1.0):
            if -0.1 <= s <= 1.1:
                normalized[dim]["score"] = max(0.0, min(1.0, s))
            else:
                return None
    return normalized


def process_response(text: str) -> dict | None:
    """Parse and normalize a model response."""
    if is_refusal(text) or not text:
        return None
    parsed = parse_json_response(text)
    if not parsed:
        return None
    return normalize_time_scores(parsed)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    if not MANIFEST_PATH.exists():
        print(f"Manifest not found: {MANIFEST_PATH}")
        sys.exit(1)

    with open(MANIFEST_PATH) as f:
        rows = list(csv.DictReader(f))
    print(f"Loaded {len(rows)} images from manifest")

    # Resume
    done_paths: set[str] = set()
    if OUTPUT_PATH.exists():
        with open(OUTPUT_PATH) as f:
            for line in f:
                try:
                    rec = json.loads(line)
                    done_paths.add(rec["image_path"])
                except (json.JSONDecodeError, KeyError):
                    pass
        print(f"Resuming: {len(done_paths)} already annotated")

    remaining = [r for r in rows if r["image_path"] not in done_paths]
    if not remaining:
        print("All images already annotated.")
        return

    print(f"Remaining: {len(remaining)}")

    model, processor = load_model()

    success = 0
    fail = 0
    prompt_stats = {"prompt_a": 0, "prompt_b": 0}
    n_batches = (len(remaining) + BATCH_SIZE - 1) // BATCH_SIZE

    with open(OUTPUT_PATH, "a") as out_f, open(SKIP_LOG_PATH, "a") as skip_f:
        for batch_start in tqdm(range(0, len(remaining), BATCH_SIZE),
                                desc="Annotating", total=n_batches):
            batch_rows = remaining[batch_start:batch_start + BATCH_SIZE]

            # Load images and build prompts for batch
            images = []
            prompts = []
            valid_indices = []
            for i, row in enumerate(batch_rows):
                img = load_image(row["image_path"])
                if img is None:
                    skip_f.write(f"OPEN_ERR\t{row['image_path']}\n")
                    fail += 1
                    continue
                prompt = PROMPT_A_BURN if is_burn(row["wound_type"]) else PROMPT_A
                images.append(img)
                prompts.append(prompt)
                valid_indices.append(i)

            if not images:
                continue

            # Batch inference with Prompt A
            try:
                responses = generate_batch(model, processor, images, prompts)
            except Exception as e:
                print(f"\n  [WARN] Batch failed: {e}")
                # Fall back to single inference for this batch
                responses = []
                for img, prompt in zip(images, prompts):
                    try:
                        responses.append(generate_single(model, processor, img, prompt))
                    except Exception:
                        responses.append("")

            # Process batch results (no fallback — pure batch speed)
            for idx_in_valid, (vi, text) in enumerate(zip(valid_indices, responses)):
                row = batch_rows[vi]
                normed = process_response(text)

                if normed is None:
                    skip_f.write(f"FAIL\t{row['image_path']}\t{text[:150]}\n")
                    fail += 1
                    continue

                prompt_stats["prompt_a"] += 1
                annotation = {
                    "image_path": row["image_path"],
                    "image_filename": row["image_filename"],
                    "wound_type": row["wound_type"],
                    "source_dataset": row["source_dataset"],
                    "split": row["split"],
                    "time_scores": normed,
                    "time_raw": text,
                    "prompt_used": "prompt_a",
                }
                out_f.write(json.dumps(annotation) + "\n")
                out_f.flush()
                success += 1

            total = success + fail
            if total > 0 and total % 500 < BATCH_SIZE:
                rate = success / total * 100
                print(f"\n  [PROGRESS] {total} done, {success} ok ({rate:.0f}%), "
                      f"A={prompt_stats['prompt_a']}, B={prompt_stats['prompt_b']}")

    print(f"\nDone. Success: {success}, Failed: {fail}")
    print(f"  Prompt A: {prompt_stats['prompt_a']}")
    print(f"  Prompt B: {prompt_stats['prompt_b']}")
    print(f"  Success rate: {success / max(1, success + fail) * 100:.1f}%")
    print(f"Annotations: {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
