"""Test 3 different prompt styles on 2 images to find what works."""

import csv
import json
import re
from pathlib import Path

from PIL import Image
import torch
from transformers import AutoProcessor, AutoModelForImageTextToText

DATA_ROOT = Path.home() / "WoundChrono" / "data"
with open(DATA_ROOT / "manifest.csv") as f:
    rows = list(csv.DictReader(f))

print("Loading model...", flush=True)
processor = AutoProcessor.from_pretrained("google/medgemma-1.5-4b-it", trust_remote_code=True)
model = AutoModelForImageTextToText.from_pretrained(
    "google/medgemma-1.5-4b-it",
    torch_dtype=torch.bfloat16,
    device_map="auto",
    trust_remote_code=True,
)
model.eval()
print("Model loaded\n", flush=True)


def gen(image, prompt, use_system=False):
    if use_system:
        msgs = [
            {"role": "system", "content": [{"type": "text", "text": "You are a medical imaging AI that analyzes wound photographs for clinical documentation."}]},
            {"role": "user", "content": [{"type": "image", "image": image}, {"type": "text", "text": prompt}]},
        ]
    else:
        msgs = [
            {"role": "user", "content": [{"type": "image", "image": image}, {"type": "text", "text": prompt}]},
        ]
    input_text = processor.apply_chat_template(msgs, add_generation_prompt=True)
    inputs = processor(text=input_text, images=[image], return_tensors="pt").to(model.device)
    with torch.no_grad():
        out = model.generate(**inputs, max_new_tokens=300, do_sample=False)
    generated = out[0][inputs["input_ids"].shape[1]:]
    return processor.decode(generated, skip_special_tokens=True).strip()


# Prompt A: descriptive without JSON template
PROMPT_A = """Describe this wound image using the TIME wound assessment framework.
For each dimension (Tissue, Inflammation, Moisture, Edge), describe what you observe and assign a score from 0.0 (worst) to 1.0 (best/healed).
Return your assessment as a JSON object."""

# Prompt B: with system message + short instruction
PROMPT_B = """Assess this wound photograph. Score each TIME dimension from 0.0 to 1.0.
T=Tissue quality, I=Inflammation level, M=Moisture balance, E=Edge advancement.
Output JSON with keys: tissue, inflammation, moisture, edge. Each has type (string) and score (float)."""

# Prompt C: minimal direct instruction
PROMPT_C = """What TIME framework scores (0.0-1.0) would you assign to this wound?
tissue score, inflammation score, moisture score, edge score.
JSON format: {"tissue":{"type":"observation","score":0.5},"inflammation":{"type":"observation","score":0.5},"moisture":{"type":"observation","score":0.5},"edge":{"type":"observation","score":0.5}}"""

prompts = [
    ("A: descriptive no-template", PROMPT_A, False),
    ("B: system msg + instruction", PROMPT_B, True),
    ("C: minimal direct", PROMPT_C, False),
]

for i in [0, 100, 500]:
    if i >= len(rows):
        break
    row = rows[i]
    img = Image.open(row["image_path"]).convert("RGB")
    print(f"=== Image {i}: {row['image_filename']} ({row['wound_type']}, {img.size}) ===", flush=True)

    for name, prompt, use_sys in prompts:
        print(f"\n  [{name}]", flush=True)
        result = gen(img, prompt, use_sys)
        print(f"  Output: {repr(result[:350])}", flush=True)

    print("\n" + "="*60, flush=True)

print("\nDone", flush=True)
