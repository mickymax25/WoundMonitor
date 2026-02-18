"""LoRA fine-tuning of MedGemma on wound/burn TIME annotations."""

from __future__ import annotations

import json
import os
import random
import sys
from pathlib import Path

import torch
from datasets import Dataset
from PIL import Image
from peft import LoraConfig, get_peft_model, TaskType
from transformers import (
    AutoModelForImageTextToText,
    AutoProcessor,
    TrainingArguments,
    Trainer,
)
from trl import SFTConfig, SFTTrainer

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DATA_ROOT = Path.home() / "WoundChrono" / "data"
ANNOTATIONS_PATH = DATA_ROOT / "annotations_time.jsonl"
OUTPUT_DIR = Path.home() / "WoundChrono" / "models" / "medgemma-wound-lora"
MODEL_ID = "google/medgemma-1.5-4b-it"
METRICS_PATH = OUTPUT_DIR / "training_metrics.json"

# LoRA config
LORA_R = 16
LORA_ALPHA = 32
LORA_DROPOUT = 0.05
LORA_TARGET_MODULES = ["q_proj", "v_proj", "k_proj", "o_proj"]

# Training config
NUM_EPOCHS = 3
BATCH_SIZE = 4
GRADIENT_ACCUMULATION = 4  # effective batch = 16
LEARNING_RATE = 2e-4
WARMUP_STEPS = 100
MAX_SEQ_LENGTH = 1024

# Task distribution (no report task — safety filter blocks report generation)
TASK_TIME = 0.85   # 85% TIME scoring
TASK_CLASS = 0.15  # 15% wound type classification

# Prompts
TIME_PROMPT = "Classify this wound using the TIME framework. Score T/I/M/E from 0.0 (worst) to 1.0 (best). Respond with JSON only."
BURN_TIME_PROMPT = "Classify this burn wound using 4 clinical dimensions (Tissue/Depth, Inflammation, Moisture, Edge/Re-epithelialization). Score from 0.0 to 1.0. Respond with JSON only."
CLASSIFICATION_PROMPT = "What type of wound is shown in this image? Respond with only the wound type category."

WOUND_TYPE_LABELS = {
    "chronic_wound": "Chronic wound",
    "diabetic_ulcer": "Diabetic foot ulcer",
    "pressure_ulcer": "Pressure ulcer",
    "venous_ulcer": "Venous leg ulcer",
    "burn_1st": "First-degree burn (superficial)",
    "burn_2nd": "Second-degree burn (partial-thickness)",
    "burn_3rd": "Third-degree burn (full-thickness)",
    "other": "Other wound type",
}


def is_burn(wound_type: str) -> bool:
    return "burn" in wound_type.lower()


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_annotations() -> tuple[list[dict], list[dict]]:
    """Load annotations and split into train/val."""
    train_data = []
    val_data = []

    with open(ANNOTATIONS_PATH) as f:
        for line in f:
            try:
                rec = json.loads(line)
            except json.JSONDecodeError:
                continue

            # Skip entries with missing TIME scores
            if not rec.get("time_scores"):
                continue

            if rec.get("split") == "val":
                val_data.append(rec)
            else:
                train_data.append(rec)

    return train_data, val_data


def build_conversation(rec: dict, task: str) -> dict | None:
    """Build a conversation dict for SFT training.

    Returns dict with 'image_path' and 'messages' (list of role/content dicts),
    or None if data is insufficient.
    """
    image_path = rec["image_path"]
    wound_type = rec["wound_type"]
    time_scores = rec["time_scores"]

    if task == "time":
        prompt = BURN_TIME_PROMPT if is_burn(wound_type) else TIME_PROMPT
        response = json.dumps(time_scores)
        return {
            "image_path": image_path,
            "messages": [
                {"role": "user", "content": prompt},
                {"role": "assistant", "content": response},
            ],
        }

    elif task == "classification":
        label = WOUND_TYPE_LABELS.get(wound_type, wound_type)
        return {
            "image_path": image_path,
            "messages": [
                {"role": "user", "content": CLASSIFICATION_PROMPT},
                {"role": "assistant", "content": label},
            ],
        }

    return None


def build_training_dataset(annotations: list[dict]) -> list[dict]:
    """Build the multi-task training dataset with proper task distribution."""
    samples = []

    for rec in annotations:
        # Assign task based on distribution
        r = random.random()
        if r < TASK_TIME:
            task = "time"
        else:
            task = "classification"

        conv = build_conversation(rec, task)
        if conv is not None:
            conv["task"] = task
            samples.append(conv)

    random.shuffle(samples)
    return samples


# ---------------------------------------------------------------------------
# Custom collator for image+text
# ---------------------------------------------------------------------------

class WoundDataCollator:
    """Collator that loads images and formats for MedGemma."""

    def __init__(self, processor):
        self.processor = processor

    def __call__(self, batch: list[dict]) -> dict:
        texts = []
        images = []

        for sample in batch:
            # Build chat-formatted text
            msgs = []
            for msg in sample["messages"]:
                if msg["role"] == "user":
                    msgs.append({
                        "role": "user",
                        "content": [
                            {"type": "image"},
                            {"type": "text", "text": msg["content"]},
                        ],
                    })
                else:
                    msgs.append({
                        "role": "assistant",
                        "content": [
                            {"type": "text", "text": msg["content"]},
                        ],
                    })

            text = self.processor.apply_chat_template(
                msgs, add_generation_prompt=False, tokenize=False
            )
            texts.append(text)

            # Load image
            try:
                img = Image.open(sample["image_path"]).convert("RGB")
            except Exception:
                # Fallback: 224x224 black image
                img = Image.new("RGB", (224, 224), (0, 0, 0))
            images.append(img)

        # Process batch — images must be nested [[img1], [img2], ...] for Gemma3
        nested_images = [[img] for img in images]
        encoding = self.processor(
            text=texts,
            images=nested_images,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=MAX_SEQ_LENGTH,
        )

        # Set labels = input_ids for causal LM training
        encoding["labels"] = encoding["input_ids"].clone()

        return encoding


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> None:
    if not ANNOTATIONS_PATH.exists():
        print(f"Annotations not found: {ANNOTATIONS_PATH}")
        print("Run 03_generate_time_annotations.py first.")
        sys.exit(1)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Set seed
    random.seed(42)
    torch.manual_seed(42)

    # Load data
    print("=== Loading annotations ===")
    train_annotations, val_annotations = load_annotations()
    print(f"  Train annotations: {len(train_annotations)}")
    print(f"  Val annotations:   {len(val_annotations)}")

    train_samples = build_training_dataset(train_annotations)
    val_samples = build_training_dataset(val_annotations)
    print(f"  Train samples (multi-task): {len(train_samples)}")
    print(f"  Val samples (multi-task):   {len(val_samples)}")

    # Task distribution stats
    from collections import Counter
    task_counts = Counter(s["task"] for s in train_samples)
    print(f"  Task distribution: {dict(task_counts)}")

    # Load model
    print("\n=== Loading model ===")
    processor = AutoProcessor.from_pretrained(MODEL_ID, trust_remote_code=True, padding_side="left")
    model = AutoModelForImageTextToText.from_pretrained(
        MODEL_ID,
        torch_dtype=torch.bfloat16,
        device_map="auto",
        trust_remote_code=True,
    )

    # Apply LoRA
    print("\n=== Applying LoRA ===")
    lora_config = LoraConfig(
        r=LORA_R,
        lora_alpha=LORA_ALPHA,
        lora_dropout=LORA_DROPOUT,
        target_modules=LORA_TARGET_MODULES,
        task_type=TaskType.CAUSAL_LM,
        bias="none",
    )
    model = get_peft_model(model, lora_config)
    model.print_trainable_parameters()

    # Training arguments
    training_args = TrainingArguments(
        output_dir=str(OUTPUT_DIR),
        num_train_epochs=NUM_EPOCHS,
        per_device_train_batch_size=BATCH_SIZE,
        per_device_eval_batch_size=BATCH_SIZE,
        gradient_accumulation_steps=GRADIENT_ACCUMULATION,
        learning_rate=LEARNING_RATE,
        warmup_steps=WARMUP_STEPS,
        lr_scheduler_type="cosine",
        bf16=True,
        logging_steps=10,
        eval_strategy="steps",
        eval_steps=200,
        save_strategy="steps",
        save_steps=200,
        save_total_limit=3,
        load_best_model_at_end=True,
        metric_for_best_model="eval_loss",
        greater_is_better=False,
        report_to="none",
        dataloader_num_workers=2,
        remove_unused_columns=False,
        gradient_checkpointing=True,
    )

    # Data collator
    collator = WoundDataCollator(processor)

    # Create HF datasets
    train_ds = Dataset.from_list(train_samples)
    val_ds = Dataset.from_list(val_samples)

    # Trainer
    print("\n=== Starting training ===")
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_ds,
        eval_dataset=val_ds,
        data_collator=collator,
    )

    train_result = trainer.train()

    # Save
    print("\n=== Saving model ===")
    trainer.save_model(str(OUTPUT_DIR))
    processor.save_pretrained(str(OUTPUT_DIR))

    # Save metrics
    metrics = {
        "train_loss": train_result.metrics.get("train_loss"),
        "train_runtime": train_result.metrics.get("train_runtime"),
        "train_samples": len(train_samples),
        "val_samples": len(val_samples),
        "epochs": NUM_EPOCHS,
        "lora_r": LORA_R,
        "lora_alpha": LORA_ALPHA,
        "learning_rate": LEARNING_RATE,
        "effective_batch_size": BATCH_SIZE * GRADIENT_ACCUMULATION,
    }

    # Eval
    eval_metrics = trainer.evaluate()
    metrics["eval_loss"] = eval_metrics.get("eval_loss")

    with open(METRICS_PATH, "w") as f:
        json.dump(metrics, f, indent=2)

    print(f"\nTraining complete.")
    print(f"  Train loss: {metrics['train_loss']:.4f}")
    print(f"  Eval loss:  {metrics['eval_loss']:.4f}")
    print(f"  LoRA adapter saved to: {OUTPUT_DIR}")
    print(f"  Metrics saved to: {METRICS_PATH}")


if __name__ == "__main__":
    main()
