"""Evaluate base vs LoRA fine-tuned MedGemma on wound TIME scoring — batch mode."""

from __future__ import annotations

import json
import random
import re
import sys
from pathlib import Path

import torch
from PIL import Image
from peft import PeftModel
from tqdm import tqdm
from transformers import AutoModelForImageTextToText, AutoProcessor

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DATA_ROOT = Path.home() / "WoundChrono" / "data"
ANNOTATIONS_PATH = DATA_ROOT / "annotations_time.jsonl"
LORA_PATH = Path.home() / "WoundChrono" / "models" / "medgemma-wound-lora"
RESULTS_PATH = DATA_ROOT / "evaluation_results.json"
MODEL_ID = "google/medgemma-1.5-4b-it"
MAX_NEW_TOKENS = 256
MAX_EVAL_SAMPLES = 200
BATCH_SIZE = 8

# Prompts
TIME_PROMPT = "Classify this wound using the TIME framework. Score T/I/M/E from 0.0 (worst) to 1.0 (best). Respond with JSON only."
BURN_TIME_PROMPT = "Classify this burn wound using 4 clinical dimensions (Tissue/Depth, Inflammation, Moisture, Edge/Re-epithelialization). Score from 0.0 to 1.0. Respond with JSON only."
CLASSIFICATION_PROMPT = "What type of wound is shown in this image? Respond with only the wound type category."

WOUND_TYPE_LABELS = {
    "chronic_wound": "chronic wound",
    "diabetic_ulcer": "diabetic foot ulcer",
    "pressure_ulcer": "pressure ulcer",
    "venous_ulcer": "venous leg ulcer",
    "burn_1st": "first-degree burn",
    "burn_2nd": "second-degree burn",
    "burn_3rd": "third-degree burn",
    "other": "other",
}


def is_burn(wound_type: str) -> bool:
    return "burn" in wound_type.lower()


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


# ---------------------------------------------------------------------------
# Model loading
# ---------------------------------------------------------------------------

def load_base_model():
    print(f"Loading base model: {MODEL_ID}")
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
    return model, processor


def load_finetuned_model():
    print(f"Loading fine-tuned model: {MODEL_ID} + {LORA_PATH}")
    processor = AutoProcessor.from_pretrained(
        MODEL_ID, trust_remote_code=True, padding_side="left"
    )
    base_model = AutoModelForImageTextToText.from_pretrained(
        MODEL_ID,
        torch_dtype=torch.bfloat16,
        device_map="auto",
        trust_remote_code=True,
    )
    model = PeftModel.from_pretrained(base_model, str(LORA_PATH))
    model.eval()
    return model, processor


# ---------------------------------------------------------------------------
# Batch inference
# ---------------------------------------------------------------------------

def generate_batch(model, processor, images: list[Image.Image], prompts: list[str]) -> list[str]:
    """Run batched inference. Returns list of decoded responses."""
    texts = []
    for prompt in prompts:
        msgs = [{"role": "user", "content": [{"type": "image"}, {"type": "text", "text": prompt}]}]
        text = processor.apply_chat_template(msgs, add_generation_prompt=True, tokenize=False)
        texts.append(text)

    # Gemma3 requires nested images: [[img1], [img2], ...]
    nested_images = [[img] for img in images]

    inputs = processor(
        text=texts,
        images=nested_images,
        return_tensors="pt",
        padding=True,
        truncation=True,
        max_length=1024,
    ).to(model.device)

    with torch.no_grad():
        output_ids = model.generate(
            **inputs,
            max_new_tokens=MAX_NEW_TOKENS,
            do_sample=False,
        )

    # Decode each response (skip input tokens)
    input_len = inputs["input_ids"].shape[1]
    results = []
    for i in range(len(images)):
        generated = output_ids[i][input_len:]
        text = processor.decode(generated, skip_special_tokens=True).strip()
        results.append(text)

    return results


# ---------------------------------------------------------------------------
# Metrics
# ---------------------------------------------------------------------------

def compute_time_mae(predicted: dict, reference: dict) -> dict[str, float]:
    dims = ["tissue", "inflammation", "moisture", "edge"]
    mae = {}
    for dim in dims:
        try:
            pred_score = float(predicted.get(dim, {}).get("score", 0))
            ref_score = float(reference.get(dim, {}).get("score", 0))
            mae[dim] = abs(pred_score - ref_score)
        except (TypeError, ValueError):
            mae[dim] = 1.0
    mae["overall"] = sum(mae[d] for d in dims) / len(dims)
    return mae


def check_classification(predicted_text: str, true_type: str) -> bool:
    pred_lower = predicted_text.lower().strip()
    true_label = WOUND_TYPE_LABELS.get(true_type, true_type).lower()
    keywords = [kw for kw in true_label.split() if len(kw) > 3]
    return any(kw in pred_lower for kw in keywords)


def avg_maes(maes: list[dict]) -> dict[str, float]:
    if not maes:
        return {"tissue": 0, "inflammation": 0, "moisture": 0, "edge": 0, "overall": 0}
    result = {}
    for key in ["tissue", "inflammation", "moisture", "edge", "overall"]:
        result[key] = sum(m[key] for m in maes) / len(maes)
    return result


# ---------------------------------------------------------------------------
# Evaluate one model (batched)
# ---------------------------------------------------------------------------

def evaluate_model(model, processor, val_data: list[dict], label: str) -> dict:
    time_maes: list[dict] = []
    class_correct = 0
    class_total = 0
    parse_failures = 0

    # Pre-load all images and prompts
    records = []
    for rec in val_data:
        try:
            img = Image.open(rec["image_path"]).convert("RGB")
        except Exception:
            continue
        prompt = BURN_TIME_PROMPT if is_burn(rec["wound_type"]) else TIME_PROMPT
        records.append({"img": img, "rec": rec, "time_prompt": prompt})

    total_batches = (len(records) + BATCH_SIZE - 1) // BATCH_SIZE

    # --- TIME scoring in batches ---
    print(f"  [{label}] TIME scoring ({len(records)} samples, batch={BATCH_SIZE})")
    for i in tqdm(range(0, len(records), BATCH_SIZE), total=total_batches, desc=f"{label} TIME"):
        batch = records[i : i + BATCH_SIZE]
        images = [r["img"] for r in batch]
        prompts = [r["time_prompt"] for r in batch]

        try:
            responses = generate_batch(model, processor, images, prompts)
        except Exception as e:
            print(f"  Batch error: {e}")
            parse_failures += len(batch)
            continue

        for r, response in zip(batch, responses):
            predicted = parse_json_response(response)
            if predicted:
                mae = compute_time_mae(predicted, r["rec"]["time_scores"])
                time_maes.append(mae)
            else:
                parse_failures += 1

    # --- Classification in batches ---
    print(f"  [{label}] Classification ({len(records)} samples, batch={BATCH_SIZE})")
    for i in tqdm(range(0, len(records), BATCH_SIZE), total=total_batches, desc=f"{label} Class"):
        batch = records[i : i + BATCH_SIZE]
        images = [r["img"] for r in batch]
        prompts = [CLASSIFICATION_PROMPT] * len(batch)

        try:
            responses = generate_batch(model, processor, images, prompts)
        except Exception as e:
            print(f"  Batch error: {e}")
            continue

        for r, response in zip(batch, responses):
            if check_classification(response, r["rec"]["wound_type"]):
                class_correct += 1
            class_total += 1

    avg = avg_maes(time_maes)
    return {
        "time_mae": avg,
        "time_parse_success_rate": (len(time_maes) / max(1, len(records))) * 100,
        "time_parse_failures": parse_failures,
        "classification_accuracy": (class_correct / max(1, class_total)) * 100,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    if not ANNOTATIONS_PATH.exists():
        print(f"Annotations not found: {ANNOTATIONS_PATH}")
        sys.exit(1)

    if not LORA_PATH.exists():
        print(f"LoRA adapter not found: {LORA_PATH}")
        sys.exit(1)

    val_data = []
    with open(ANNOTATIONS_PATH) as f:
        for line in f:
            try:
                rec = json.loads(line)
                if rec.get("split") == "val" and rec.get("time_scores"):
                    val_data.append(rec)
            except json.JSONDecodeError:
                continue

    if len(val_data) > MAX_EVAL_SAMPLES:
        random.seed(42)
        val_data = random.sample(val_data, MAX_EVAL_SAMPLES)

    print(f"Evaluating on {len(val_data)} validation samples (batch={BATCH_SIZE})\n")

    # Base model
    print("=== BASE MODEL ===")
    base_model, base_proc = load_base_model()
    base_results = evaluate_model(base_model, base_proc, val_data, "Base")
    del base_model
    torch.cuda.empty_cache()

    # Fine-tuned model
    print("\n=== FINE-TUNED MODEL ===")
    ft_model, ft_proc = load_finetuned_model()
    ft_results = evaluate_model(ft_model, ft_proc, val_data, "LoRA")
    del ft_model
    torch.cuda.empty_cache()

    # Improvements
    base_mae = base_results["time_mae"]
    ft_mae = ft_results["time_mae"]
    improvement = {
        "time_mae_reduction": {
            dim: base_mae[dim] - ft_mae[dim]
            for dim in ["tissue", "inflammation", "moisture", "edge", "overall"]
        },
        "classification_accuracy_gain": ft_results["classification_accuracy"] - base_results["classification_accuracy"],
        "parse_rate_gain": ft_results["time_parse_success_rate"] - base_results["time_parse_success_rate"],
    }

    all_results = {
        "eval_samples": len(val_data),
        "base_model": base_results,
        "finetuned_model": ft_results,
        "improvement": improvement,
    }
    with open(RESULTS_PATH, "w") as f:
        json.dump(all_results, f, indent=2)

    # Summary
    print("\n" + "=" * 60)
    print("EVALUATION RESULTS")
    print("=" * 60)
    print(f"Samples: {len(val_data)}")

    print("\n--- TIME MAE (lower is better) ---")
    header = f"{'Dimension':<16} {'Base':>8} {'LoRA':>8} {'Delta':>8}"
    print(header)
    print("-" * len(header))
    for dim in ["tissue", "inflammation", "moisture", "edge", "overall"]:
        delta = base_mae[dim] - ft_mae[dim]
        sign = "+" if delta > 0 else ""
        print(f"{dim:<16} {base_mae[dim]:>8.4f} {ft_mae[dim]:>8.4f} {sign}{delta:>7.4f}")

    print(f"\n--- Parse Success Rate ---")
    print(f"  Base: {base_results['time_parse_success_rate']:.1f}%")
    print(f"  LoRA: {ft_results['time_parse_success_rate']:.1f}%")

    print(f"\n--- Classification Accuracy ---")
    print(f"  Base: {base_results['classification_accuracy']:.1f}%")
    print(f"  LoRA: {ft_results['classification_accuracy']:.1f}%")
    print(f"  Gain: {improvement['classification_accuracy_gain']:+.1f}%")

    print(f"\nResults saved to: {RESULTS_PATH}")


if __name__ == "__main__":
    main()
