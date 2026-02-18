"""Quick diagnostic script — run on the GCP VM to see raw MedGemma output.

Usage:
    python3 scripts/test_inference_debug.py [path/to/wound_image.jpg]

If no image path is given, generates a synthetic test image.
Tests all 3 inference modes: TIME classification, report generation, contradiction.
Prints raw model output for debugging JSON parsing issues.
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import torch
from PIL import Image

# Add backend to path so we can import the parsing helpers
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
from app.models.medgemma import (
    TIME_CLASSIFICATION_PROMPT,
    parse_time_json,
    parse_json_safe,
    _strip_thinking,
    _extract_json_block,
    _normalize_time_scores,
    _extract_scores_regex,
)


def load_model():
    from transformers import AutoProcessor, AutoModelForImageTextToText

    model_id = "google/medgemma-1.5-4b-it"
    print(f"Loading {model_id}...", flush=True)
    processor = AutoProcessor.from_pretrained(
        model_id, trust_remote_code=True, padding_side="left",
    )
    model = AutoModelForImageTextToText.from_pretrained(
        model_id,
        torch_dtype=torch.bfloat16,
        device_map="auto",
        trust_remote_code=True,
    )
    model.eval()
    print(f"Model loaded on {model.device}", flush=True)
    return model, processor


def generate(model, processor, image: Image.Image, prompt: str, max_new_tokens: int = 512):
    messages = [
        {
            "role": "user",
            "content": [
                {"type": "image"},
                {"type": "text", "text": prompt},
            ],
        }
    ]
    input_text = processor.apply_chat_template(
        messages, add_generation_prompt=True, tokenize=False,
    )
    inputs = processor(
        text=input_text,
        images=[[image]],
        return_tensors="pt",
    ).to(model.device)

    t0 = time.time()
    with torch.no_grad():
        output_ids = model.generate(
            **inputs, max_new_tokens=max_new_tokens, do_sample=False,
        )
    elapsed = time.time() - t0

    generated = output_ids[0][inputs["input_ids"].shape[1]:]

    # Decode WITH special tokens to see what the model actually outputs
    raw_with_special = processor.decode(generated, skip_special_tokens=False)
    # Decode WITHOUT special tokens (what our backend does)
    raw_clean = processor.decode(generated, skip_special_tokens=True).strip()

    return raw_with_special, raw_clean, elapsed


def main():
    # Load image
    if len(sys.argv) > 1:
        img_path = sys.argv[1]
        print(f"Loading image: {img_path}")
        image = Image.open(img_path).convert("RGB")
    else:
        print("No image provided, using synthetic 256x256 red/pink gradient")
        import numpy as np
        arr = np.zeros((256, 256, 3), dtype=np.uint8)
        arr[:, :, 0] = 180  # reddish
        arr[:, :, 1] = np.linspace(80, 140, 256).astype(np.uint8)  # gradient
        arr[:, :, 2] = 100
        image = Image.fromarray(arr)

    print(f"Image size: {image.size}\n")

    model, processor = load_model()

    # =========================================================================
    # Test 1: TIME Classification
    # =========================================================================
    print("=" * 70)
    print("TEST 1: TIME CLASSIFICATION")
    print("=" * 70)

    raw_special, raw_clean, elapsed = generate(model, processor, image, TIME_CLASSIFICATION_PROMPT)
    print(f"\nGeneration time: {elapsed:.1f}s")
    print(f"\n--- Raw output WITH special tokens ---")
    print(repr(raw_special[:1000]))
    print(f"\n--- Raw output WITHOUT special tokens (what backend sees) ---")
    print(repr(raw_clean[:1000]))

    # Test our parsing pipeline
    print(f"\n--- Parsing pipeline ---")
    stripped = _strip_thinking(raw_clean)
    print(f"After _strip_thinking: {repr(stripped[:500])}")

    extracted = _extract_json_block(raw_clean)
    print(f"After _extract_json_block: {repr(extracted[:500])}")

    try:
        result = parse_time_json(raw_clean)
        print(f"\nparse_time_json SUCCESS: {json.dumps(result, indent=2)}")
    except ValueError as e:
        print(f"\nparse_time_json FAILED: {e}")
        # Try regex fallback
        regex_result = _extract_scores_regex(raw_clean)
        if regex_result:
            print(f"Regex fallback SUCCESS: {json.dumps(regex_result, indent=2)}")
        else:
            print("Regex fallback also FAILED")

    # Try with JSON parse + normalize (like annotation script)
    try:
        data = json.loads(extracted)
        normalized = _normalize_time_scores(data)
        if normalized:
            print(f"Manual normalize SUCCESS: {json.dumps(normalized, indent=2)}")
        else:
            print(f"Manual normalize FAILED — parsed keys: {list(data.keys())}")
            print(f"Parsed data: {json.dumps(data, indent=2)[:500]}")
    except json.JSONDecodeError as e:
        print(f"Manual JSON parse FAILED: {e}")

    # =========================================================================
    # Test 2: Report Generation
    # =========================================================================
    print("\n" + "=" * 70)
    print("TEST 2: REPORT GENERATION")
    print("=" * 70)

    report_prompt = (
        "You are a wound care specialist. Analyze the wound image and data below.\n"
        "Respond with a JSON object ONLY. No markdown, no explanation outside the JSON.\n\n"
        "## TIME Classification\n"
        "- Tissue: granulation (score 0.60)\n"
        "- Inflammation: mild erythema (score 0.70)\n"
        "- Moisture: balanced (score 0.80)\n"
        "- Edge: advancing (score 0.50)\n\n"
        "## Trajectory: stable\n\n"
        'Respond with this exact JSON structure:\n'
        '{"summary": "2-3 sentence clinical summary",'
        ' "wound_status": "current status",'
        ' "change_analysis": "change since last visit",'
        ' "interventions": ["intervention 1", "intervention 2"],'
        ' "follow_up": "follow-up timeline"}'
    )
    raw_special, raw_clean, elapsed = generate(model, processor, image, report_prompt, max_new_tokens=1000)
    print(f"\nGeneration time: {elapsed:.1f}s")
    print(f"\n--- Raw output (clean, first 800 chars) ---")
    print(repr(raw_clean[:800]))

    result = parse_json_safe(raw_clean)
    if result and "summary" in result:
        print(f"\nReport parse SUCCESS: {json.dumps(result, indent=2)[:500]}")
    else:
        print(f"\nReport parse FAILED — got keys: {list(result.keys()) if result else 'empty'}")

    # =========================================================================
    # Test 3: Contradiction Detection
    # =========================================================================
    print("\n" + "=" * 70)
    print("TEST 3: CONTRADICTION DETECTION")
    print("=" * 70)

    contra_prompt = (
        "The AI wound assessment determined the trajectory is 'deteriorating'. "
        "The nurse recorded the following notes: 'Wound looks much better today, "
        "good granulation tissue forming'. "
        "Is there a meaningful contradiction between the AI assessment and nurse notes? "
        'Respond with JSON only: {"contradiction": true, "detail": "explanation"} '
        'or {"contradiction": false, "detail": null}'
    )
    raw_special, raw_clean, elapsed = generate(model, processor, image, contra_prompt, max_new_tokens=200)
    print(f"\nGeneration time: {elapsed:.1f}s")
    print(f"\n--- Raw output (clean) ---")
    print(repr(raw_clean[:500]))

    result = parse_json_safe(raw_clean)
    print(f"\nContradiction parse: {result}")

    print("\n" + "=" * 70)
    print("ALL TESTS COMPLETE")
    print("=" * 70)


if __name__ == "__main__":
    main()
