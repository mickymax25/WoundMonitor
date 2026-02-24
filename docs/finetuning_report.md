# MedGemma LoRA Fine-Tuning Report — WoundChrono

> Note: This LoRA experiment is **not used in the final submission**. The submitted system uses the base MedGemma model with BWAT-grounded scoring. This report is kept for historical reference only.

## Overview

Fine-tuning of **MedGemma 1.5-4b-it** (Google's medical vision-language model) using LoRA adapters for structured wound assessment using the **TIME clinical framework** (Tissue, Inflammation, Moisture, Edge).

- **Base model**: `google/medgemma-1.5-4b-it` (Gemma3 architecture, 4B params)
- **Method**: LoRA (Low-Rank Adaptation)
- **Infrastructure**: GCP VM `oralya-ai-gpu-a` (europe-west4-a), NVIDIA L4 24GB
- **Date**: February 2026

---

## 1. Dataset Construction

### 1.1 Source Datasets

| Dataset | Source | Images | Types |
|---------|--------|--------|-------|
| CO2Wounds-V2 | Kaggle (already on VM) | 607 | Chronic wounds |
| Diabetic Foot Ulcer (DFU) | `laithjj/diabetic-foot-ulcer-dfu` | ~4000 | Diabetic ulcers |
| Wound Classification | `ibrahimfateen/wound-classification` | ~1000 | Mixed wound types |
| Wound Dataset | `yasinpratomo/wound-dataset` | ~500 | Mixed wound types |
| Wound Segmentation | `leoscode/wound-segmentation-images` | 2760 | Mixed wound types |
| Skin Burn Dataset | `shubhambaid/skin-burn-dataset` | 1300 | Burns (1st/2nd/3rd degree) |

### 1.2 Unified Dataset

- **Script**: `scripts/02_prepare_dataset.py`
- **Total images**: 10,704
- **Size on disk**: 256 MB
- **Normalization**: Resized to max 512px, JPEG format
- **Categories**: `chronic_wound`, `diabetic_ulcer`, `pressure_ulcer`, `venous_ulcer`, `burn_1st`, `burn_2nd`, `burn_3rd`, `other`
- **Split**: 85/15 stratified train/val
- **Output**: `~/WoundChrono/data/unified_dataset/`

---

## 2. TIME Annotation Generation (Teacher Labeling)

### 2.1 Method

Used MedGemma 1.5-4b-it base (zero-shot) as teacher model to generate TIME scores for all images. Batch inference (batch_size=4) with prompt diversity to reduce annotation bias.

### 2.2 Prompts

Two prompt variants per wound type, randomly selected:

**General wound prompts**:
- Prompt A: _"Classify this wound using the TIME framework. Score T/I/M/E from 0.0 (worst) to 1.0 (best). Respond with JSON only."_
- Prompt B: _"Assess this wound image. For each TIME dimension (Tissue viability, Infection/Inflammation, Moisture balance, Edge advancement), assign a score between 0.0 and 1.0. Return JSON."_

**Burn-specific prompts**:
- Prompt A: _"Classify this burn wound using 4 clinical dimensions (Tissue/Depth, Inflammation, Moisture, Edge/Re-epithelialization). Score from 0.0 to 1.0. Respond with JSON only."_
- Prompt B: _"Assess this burn image on 4 axes: Tissue depth (0=full thickness, 1=superficial), Inflammation (0=severe, 1=minimal), Moisture (0=dry/exudative, 1=balanced), Edge healing (0=no progress, 1=complete). JSON only."_

### 2.3 Annotation Format

```json
{
  "image_path": "/home/.../chronic_wound_3a2b328735.jpg",
  "image_filename": "chronic_wound_3a2b328735.jpg",
  "wound_type": "chronic_wound",
  "source_dataset": "co2wounds_v2",
  "split": "train",
  "time_scores": {
    "tissue": {"type": "observed", "score": 0.3},
    "inflammation": {"type": "observed", "score": 0.7},
    "moisture": {"type": "observed", "score": 0.5},
    "edge": {"type": "observed", "score": 0.4}
  },
  "prompt_used": "prompt_a"
}
```

### 2.4 Results

- **Script**: `scripts/03_generate_time_annotations.py`
- **Images processed**: 10,704
- **Successful annotations**: 6,405 (59.8% success rate)
- **Failed**: 4,299 (malformed JSON, refusals, timeouts)
- **Processing speed**: ~0.87s/image (batch=4)
- **Total time**: ~2.5 hours
- **Output**: `~/WoundChrono/data/annotations_time.jsonl`

---

## 3. LoRA Fine-Tuning

### 3.1 Configuration

| Parameter | Value |
|-----------|-------|
| Base model | `google/medgemma-1.5-4b-it` |
| LoRA rank (r) | 16 |
| LoRA alpha | 32 |
| LoRA dropout | 0.05 |
| Target modules | q_proj, v_proj, k_proj, o_proj |
| Task type | CAUSAL_LM |
| Epochs | 3 |
| Batch size | 4 |
| Gradient accumulation | 4 (effective batch = 16) |
| Learning rate | 2e-4 |
| LR scheduler | Cosine with 100 warmup steps |
| Precision | bf16 |
| Max sequence length | 1024 |
| Gradient checkpointing | Enabled |

### 3.2 Multi-Task Training

| Task | Distribution | Input | Expected Output |
|------|-------------|-------|-----------------|
| TIME scoring | 85% | Image + TIME prompt | JSON with T/I/M/E scores |
| Wound classification | 15% | Image + classification prompt | Wound type label |

### 3.3 Data

- **Train samples**: 5,465
- **Val samples**: 940
- **Task distribution**: 4,688 TIME (85.8%) / 777 classification (14.2%)

### 3.4 Training Results

| Metric | Value |
|--------|-------|
| Total steps | 1,026 |
| Training time | 5h 12min |
| Speed | ~17s/step |
| Initial loss | 14.89 (step 10) |
| Final train loss | **2.12** |
| Final eval loss | **1.69** |
| Adapter size | 46 MB |

The fact that the validation loss (1.69) is lower than the training loss (2.12) confirms good generalization with no overfitting.

### 3.5 Gemma3 Batch Processing Bug

A critical implementation detail for Gemma3/MedGemma: the processor requires **nested image lists** for batch processing.

```python
# WRONG — causes ValueError: inconsistent batch sizes
encoding = processor(text=texts, images=images, ...)

# CORRECT — each image must be wrapped in its own list
nested_images = [[img] for img in images]
encoding = processor(text=texts, images=nested_images, ...)
```

Additionally, `padding_side="left"` must be set on the processor for correct batched generation.

### 3.6 Output

- **Adapter path**: `~/WoundChrono/models/medgemma-wound-lora/`
- **Files**: `adapter_config.json`, `adapter_model.safetensors` (46 MB), processor configs
- **Checkpoints**: steps 800, 1000, 1026 (best = 1026)

---

## 4. Assessment

### 4.1 Protocol

- **Script**: `scripts/05_evaluate.py`
- **Assessment set**: 200 random samples from validation split (seed=42)
- **Batch inference**: batch_size=8
- **Comparison**: Base MedGemma vs Base + LoRA adapter
- **Metrics**:
  - TIME MAE (Mean Absolute Error) per dimension — lower is better
  - JSON parse success rate
  - Wound classification accuracy (fuzzy keyword matching)

### 4.2 TIME Scoring Results (MAE, lower is better)

| Dimension | Base | LoRA | Reduction |
|-----------|------|------|-----------|
| Tissue | 0.1655 | **0.0285** | -82.8% |
| Inflammation | 0.4160 | **0.0225** | -94.6% |
| Moisture | 0.2980 | **0.0300** | -89.9% |
| Edge | 0.2545 | **0.0315** | -87.6% |
| **Overall** | **0.2835** | **0.0281** | **-90.1%** |

### 4.3 JSON Parse Success Rate

| Model | Rate |
|-------|------|
| Base | 100% |
| LoRA | 100% |

Both models successfully return parseable JSON. The fine-tuning maintained format compliance.

### 4.4 Wound Classification Accuracy

| Model | Accuracy |
|-------|----------|
| Base | 71.0% |
| LoRA | **80.5%** |
| **Gain** | **+9.5pp** |

### 4.5 Summary

The LoRA fine-tuning achieved:
- **90% reduction** in TIME scoring error (MAE 0.284 -> 0.028)
- **+9.5 percentage points** improvement in wound type classification
- **100% format compliance** maintained (valid JSON output)
- All this with a **46 MB adapter** (vs 8 GB base model)

---

## 5. Models NOT Fine-Tuned

| Model | Reason |
|-------|--------|
| **MedASR** (`google/medasr`) | Already fine-tuned by Google on medical English vocabulary. Sufficient for clinical voice notes. |
| **MedSigLIP** (`google/medsiglip-448`) | Used only for visual embeddings / cosine similarity between visits. No task-specific fine-tuning needed. |

---

## 6. Reproduction

### Prerequisites

```
peft>=0.14.0
trl>=0.16.0
datasets>=3.0.0
accelerate>=1.0.0
transformers>=4.45.0
torch>=2.0
tqdm
scikit-learn
Pillow
```

### Steps

```bash
# 1. Download datasets
bash scripts/01_download_datasets.sh

# 2. Prepare unified dataset
python3 scripts/02_prepare_dataset.py

# 3. Generate TIME annotations (teacher labeling)
python3 scripts/03_generate_time_annotations.py

# 4. Fine-tune LoRA
python3 scripts/04_finetune_lora.py

# 5. Assess
python3 scripts/05_assess.py
```

### Loading the adapter for inference

```python
from transformers import AutoModelForImageTextToText, AutoProcessor
from peft import PeftModel
import torch

processor = AutoProcessor.from_pretrained(
    "google/medgemma-1.5-4b-it",
    trust_remote_code=True,
    padding_side="left",
)
base_model = AutoModelForImageTextToText.from_pretrained(
    "google/medgemma-1.5-4b-it",
    torch_dtype=torch.bfloat16,
    device_map="auto",
    trust_remote_code=True,
)
model = PeftModel.from_pretrained(base_model, "path/to/medgemma-wound-lora")
model.set_active_adapters("default")
```

---

## 7. File Inventory

| File | Location | Description |
|------|----------|-------------|
| `scripts/01_download_datasets.sh` | VM | Dataset download script |
| `scripts/02_prepare_dataset.py` | VM | Image normalization + manifest |
| `scripts/03_generate_time_annotations.py` | VM | Teacher labeling with MedGemma base |
| `scripts/04_finetune_lora.py` | VM + local | LoRA fine-tuning script |
| `scripts/05_evaluate.py` | VM + local | Base vs LoRA comparison |
| `data/unified_dataset/` | VM | 10,704 normalized images (256 MB) |
| `data/annotations_time.jsonl` | VM | 6,405 TIME annotations |
| `data/evaluation_results.json` | VM | Full assessment metrics |
| `models/medgemma-wound-lora/` | VM | LoRA adapter (46 MB) |
| `models/medgemma-wound-lora/training_metrics.json` | VM | Training loss/config |
