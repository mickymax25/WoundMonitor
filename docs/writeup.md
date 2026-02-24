# Wound Monitor: Objective Wound Trajectory Assessment Using Three HAI-DEF Models

## 1. The Problem

Chronic wounds affect millions of patients and drive avoidable amputations, infections, and prolonged hospitalizations. The decision to escalate care often depends on whether a wound is improving, static, or worsening — yet the evaluation is still subjective. Two clinicians assessing the same wound routinely disagree.

The TIME framework (Tissue, Inflammation/Infection, Moisture, Edge) provides shared vocabulary, but it does **not** provide a numeric, reproducible scale. Wound Monitor addresses this gap by using **BWAT (Bates-Jensen Wound Assessment Tool)** as the primary numeric scale (13 items, 1–5 each, total 13–65), then deriving TIME composites for intuitive visualization.

## 2. The Solution

### Architecture

Wound Monitor is a Progressive Web App that orchestrates three Google HAI-DEF models (MedGemma, MedSigLIP, MedASR) in a structured agent pipeline:

| Model | Role | Parameters |
|---|---|---|
| **MedGemma 1.5 4B-IT (base)** | BWAT item observations (JSON), clinical report generation, contradiction detection, clinical Q&A | 4B |
| **MedSigLIP 0.9B** | Wound image embeddings for change detection + zero-shot visual hints | 0.9B |
| **MedASR 105M** | Nurse voice note transcription | 105M |

### Pipeline

WoundAgent orchestrates these models into a robust, observable pipeline:

1. **MedSigLIP embedding** for change detection and visual similarity.
2. **MedGemma observation extraction**: base model produces BWAT item observations (JSON).
3. **Deterministic BWAT scoring** from observations (13–65 total), with per‑item scores.
4. **TIME composites** derived from BWAT items (for intuitive trend display only).
5. **Previous assessment retrieval** for trajectory computation.
6. **Trajectory computation** using BWAT change + TIME composite shifts + embedding distance.
7. **MedASR transcription** of nurse dictation.
8. **Contradiction detection** (rule‑based first, LLM fallback).
9. **Structured clinical report** with recommendations and follow‑up.
10. **Alerting + Critical Mode**: red‑flag detection (e.g., necrosis, maggots) triggers immediate referral flow and simplified UI.

**Contradiction example**: A nurse dictates “wound looks better” while the AI detects worsening BWAT items. The discrepancy is surfaced as a contradiction alert.

**Critical mode**: When a red‑flag visual cue is detected, the UI collapses into a “critical” state with a direct physician referral CTA and disables non‑essential UI.

### Care Loop: Patient, Nurse, Specialist

**Patient self‑reporting.** Each patient receives a unique shareable link (token‑based, no login). Patients photograph their wound between visits and submit with an optional note. Submissions are tagged `source: patient` and tracked separately.

**Nurse analysis with clinical Q&A.** The nurse photographs the wound, optionally dictates via MedASR, and receives BWAT scores, trajectory, contradiction flags, report, and alert level. When notes contain clinical questions, the system triggers a dedicated MedGemma call to answer them.

**Physician referral.** When the alert triggers (or critical mode is active), the nurse sends a one‑tap referral via call, WhatsApp, or email — pre‑populated with physician details and urgency level.

### Technical Stack

FastAPI + Next.js 14 PWA, deployed on a single NVIDIA L4 GPU (24GB). MedGemma bfloat16 (~8.6GB VRAM), MedSigLIP offloaded to CPU (~3.5GB RAM). The pipeline adapts automatically for burns using burn‑specific MedSigLIP labels and prompts.

## 3. Results and Impact

We validated the system end‑to‑end with real model inference on a GCP g2‑standard‑4 (NVIDIA L4). The current submission focuses on **BWAT‑grounded scoring** with deterministic item conversion and a critical red‑flag path.

### Pilot Evaluation (Qualitative)

- **Structured output reliability**: BWAT item JSON extraction + deterministic scoring yields stable totals across repeated runs.
- **Critical safety**: severe cases trigger critical mode and immediate referral flow.
- **Trajectory signal**: BWAT totals + TIME composites provide interpretable trend signals across visits.

### Health Equity Impact

- **Democratizing expertise**: smartphone‑based BWAT assessment without specialized certification
- **Reducing variability**: same photo, same scores, regardless of who uploads it
- **Active decision support**: nurse questions answered with evidence from image + scores
- **Early detection**: quantitative trajectory catches stagnation before subjective observation
- **Edge‑ready**: single consumer GPU, no cloud dependency, patient data stays local

### Limitations

- **Clinical validation**: BWAT scores are not a diagnosis; expert consensus validation required
- **Latency**: full pipeline still tens of seconds; reducible via model distillation
- **Measurement**: no true area/depth measurement yet; staging and segmentation planned
- **Regulatory**: positioned as clinical decision support; autonomous use requires regulatory clearance

---

## Appendix — Historical LoRA Experiment (Not Used In Final Submission)

We previously fine‑tuned MedGemma 1.5 4B‑IT with LoRA to regress TIME scores (0–1). That experiment improved agreement with teacher labels but introduced instability when confronted with out‑of‑distribution imagery. For this submission we **disabled LoRA** and grounded scoring in BWAT + deterministic conversion.
