# Wound Monitor: Objective Wound Trajectory Assessment Using Three HAI-DEF Models

## 1. The Problem

Chronic wounds affect 8.2 million patients in the United States alone, costing over $28 billion annually. Venous ulcers, diabetic foot ulcers, and pressure injuries often persist for months or years, with 30% five-year mortality rivaling many cancers. Whether these wounds are improving, stagnating, or deteriorating determines treatment escalation, specialist referrals, and ultimately, whether a patient keeps a limb.

**The fundamental obstacle is measurement.** Today's wound assessment is subjective and non-quantitative. Two clinicians evaluating the same wound routinely disagree on tissue type, inflammation severity, and trajectory. The TIME framework (Tissue, Inflammation/Infection, Moisture, Edge) provides structured vocabulary, but scoring remains observer-dependent. In resource-limited settings, the clinician may be a community health worker with minimal wound training, making consistent longitudinal assessment even harder.

Wound Monitor transforms a smartphone photograph into an objective, reproducible wound trajectory measurement using three Google HAI-DEF models working in concert, with a domain-adapted model fine-tuned specifically for wound assessment.

## 2. The Solution

### Architecture

Wound Monitor is a Progressive Web App that orchestrates three HAI-DEF models (MedGemma, MedSigLIP, MedASR) in a ten-step agent pipeline:

| Model | Role | Parameters |
|---|---|---|
| **MedGemma 1.5 4B-IT** | TIME scoring (LoRA), clinical descriptions (base), report generation, contradiction detection | 4B + 46MB LoRA adapter |
| **MedSigLIP 0.9B** | Wound image embeddings for change detection + zero-shot classification | 0.9B |
| **MedASR 105M** | Nurse voice note transcription | 105M |

MedGemma is used in three modes within a single inference session via PEFT adapter toggling: **(a)** the LoRA-adapted model produces TIME scores, **(b)** the base model generates clinical descriptions informed by those scores, and **(c)** the base model answers nurse questions with evidence-based clinical guidance --- no reload required, all three modes on a single GPU.

### Pipeline

WoundAgent is a multi-model orchestration agent that dynamically routes inference across three HAI-DEF models, toggles LoRA adapters at runtime, and conditionally triggers dedicated reasoning calls based on clinical context. For each visit: **(1)** MedSigLIP embedding, **(2)** MedGemma TIME scoring via LoRA (T/I/M/E, each 0-1), **(3)** clinical descriptions via base model, **(4)** previous assessment retrieval, **(5)** trajectory computation (mean TIME delta thresholds + cosine distance), **(6)** MedASR nurse dictation transcription, **(7)** contradiction detection (rule-based first, LLM fallback), **(8)** structured clinical report, **(9)** nurse clinical Q&A if questions detected, **(10)** alert level determination (red/orange/yellow/green with explicit thresholds).

**Contradiction example**: A nurse dictated "wound looks better this week" while the AI detected a 0.15-point inflammation increase and classified the trajectory as deteriorating --- triggering an orange alert. This could indicate early subclinical infection or contextual information the AI cannot access (e.g., recent debridement). Either way, the divergence warrants attention.

**Nurse Q&A example**: A nurse dictated "Should I switch to foam dressing? Is there any sign of infection?" The system answered using the wound image and TIME scores: (1) "An alginate or hydrocolloid would better manage the exudate given tissue score 0.2 (slough with necrosis)." (2) "Inflammation 0.8 shows moderate erythema; if accompanied by purulent discharge, antibiotics warranted."

### LoRA Fine-Tuning

We fine-tuned MedGemma 1.5 4B-IT on 5,000 wound images from 6 public datasets (CO2Wounds-V2, Diabetic Foot Ulcer, Wound Classification, Wound Dataset, Wound Segmentation, Skin Burn) using LoRA (rank 16, alpha 32) on q/k/v/o projections. Training objective: regression on TIME scores annotated using the base model as teacher with manual edge-case correction. The adapter (46MB) achieves MAE 0.028 against teacher labels --- measuring adaptation fidelity, not clinical ground truth (see Limitations).

### Care Loop: Patient, Nurse, Specialist

**Patient self-reporting.** Each patient receives a unique shareable link (token-based, no login). Patients photograph their wound between visits and submit with an optional note. The interface masks the patient's name for privacy. Submissions are tagged `source: patient` and tracked separately.

**Nurse analysis with clinical Q&A.** The nurse photographs the wound, optionally dictates via MedASR, and receives TIME scores, trajectory, contradiction flags, report, and alert level. When nurse notes contain clinical questions, the system detects them and triggers a dedicated MedGemma base-model call: given the wound image and TIME scores as context, it answers each question specifically in a "Clinical Guidance" report section --- transforming passive reporting into active clinical decision support.

**Physician referral.** When the alert triggers, the nurse sends a one-tap referral via call, WhatsApp, or email --- pre-populated with the physician's details and urgency level. The specialist receives a clinical summary page with TIME scores, trajectory, AI report, nurse notes, and clinical Q&A responses. Three actors, one continuous data pipeline.

### Technical Stack

FastAPI + Next.js 14 PWA, deployed on a single NVIDIA L4 GPU (24GB). MedGemma bfloat16 (~8.6GB VRAM), MedSigLIP offloaded to CPU (~3.5GB RAM). The pipeline adapts automatically for burns via burn-specific MedSigLIP labels and burn care specialist prompts.

## 3. Results and Impact

We deployed Wound Monitor on a GCP g2-standard-4 instance (NVIDIA L4) and validated end-to-end with real model inference (no mocks):

| Metric | Value |
|---|---|
| TIME scoring MAE (LoRA vs. teacher) | 0.028 |
| TIME descriptions | Model-generated, 2-4 word clinical findings |
| Zero-shot classification | 8 wound + 8 burn categories (MedSigLIP) |
| Full pipeline latency | ~60s avg (MedSigLIP ~5s, LoRA ~20s, descriptions ~4s, report ~25s) |
| Nurse Q&A | Questions auto-detected, answered via dedicated inference call |
| Care loop | Patient self-report + nurse analysis + physician referral |
| Alert system | 4 levels with explicit thresholds |

### Plausibility Validation (N=30)

30 real-inference analyses on 20 patients (10 with 2 visits, 10 baseline). Chronic wounds, diabetic ulcers, and burns.

| Metric | Result |
|---|---|
| TIME scoring success rate | 80% (24/30 produced valid scores) |
| Tissue score range | 0.20--0.50 (mean 0.35, excluding failures) |
| Inflammation score range | 0.50--0.80 (mean 0.66) |
| Trajectory detection | Correctly identified 2 improving, 2 deteriorating, 3 stable |
| Contradiction detection | 3/10 visit-2 assessments flagged (nurse-AI divergence) |
| Alert distribution | 4 red, 3 orange, 5 yellow, 18 green |
| Average latency | 58.8s per full analysis |

Six assessments (20%) returned default scores due to parsing failures; these were correctly escalated as red alerts. The zero-shot fallback (MedSigLIP classification mapped to approximate TIME scores) was implemented post-study to address this.

### Health Equity Impact

- **Democratizing expertise**: Smartphone-based TIME assessment without specialized certification
- **Reducing variability**: Same photo, same scores, regardless of who uploads it
- **Active decision support**: Nurse asks clinical questions, AI answers with evidence from the wound image
- **Early detection**: Quantitative trajectory catches stagnation before subjective observation
- **Edge-ready**: Single consumer GPU, no cloud dependency, patient data stays local

### Limitations

- **Clinical validation**: MAE 0.028 measures teacher agreement, not clinical ground truth; expert consensus validation required
- **Latency**: ~60s per assessment (~120s with nurse Q&A); reducible via model distillation
- **Wound measurement**: No area/depth measurement; pressure ulcer staging planned as extension
- **Regulatory**: Positioned as clinical decision support under FDA 21st Century Cures Act CDS exemption; formal regulatory pathway needed for autonomous use

Wound Monitor demonstrates that three HAI-DEF models, orchestrated in a purpose-built agent pipeline with domain-specific fine-tuning, can transform subjective wound assessment into objective, reproducible trajectory measurement --- the missing instrument in chronic wound care.
