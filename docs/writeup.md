# Wound Monitor — Objective Wound Trajectory Assessment with Three HAI‑DEF Models

## TL;DR
Wound Monitor is a PWA that converts a wound photo into a **numeric, reproducible** severity score using the 13‑item **BWAT** scale (13–65) and derives **TIME composites** for intuitive trends. It orchestrates **MedGemma (reasoning + structured observations), MedSigLIP (visual change), and MedASR (nurse dictation)** and includes a **Critical Mode** for red‑flag findings with one‑tap referral.

---

## 1. The Problem
Chronic wound care depends on knowing whether a wound is improving, stable, or deteriorating — yet assessments are still subjective. The TIME framework (Tissue, Inflammation/Infection, Moisture, Edge) helps clinicians speak the same language, but **TIME alone is not a numeric, reproducible scale**.

## 2. The Solution
We use **BWAT** as the primary numeric scale (13 items × 1–5, total 13–65), then **derive TIME composites** for visualization and communication. This produces a consistent numeric trajectory while retaining clinician‑friendly vocabulary.

### Key Innovations
- **BWAT‑grounded scoring from vision‑language observations** (MedGemma base → JSON observations → deterministic BWAT item scoring).
- **Critical Mode** for red‑flag findings (necrosis, maggots, gross infection) that collapses UI and triggers immediate referral.
- **Contradiction detection** between nurse narrative and model‑derived trajectory.
- **End‑to‑end care loop**: patient self‑report → nurse assessment → specialist referral.

### Architecture (Three HAI‑DEF Models)

| Model | Role | Parameters |
|---|---|---|
| **MedGemma 1.5 4B‑IT (base)** | BWAT item observations (JSON), report generation, contradiction detection, clinical Q&A | 4B |
| **MedSigLIP 0.9B** | Image embeddings for visual similarity + change detection | 0.9B |
| **MedASR 105M** | Nurse voice note transcription | 105M |

### Pipeline (Per Visit)
1. **MedSigLIP embedding** for visual change detection.
2. **MedGemma observation extraction** → BWAT item observations (JSON).
3. **Deterministic BWAT scoring** (13–65) with per‑item scores.
4. **TIME composites** derived from BWAT (for trend UI only).
5. **Previous visit retrieval** and trajectory computation.
6. **MedASR transcription** of nurse dictation.
7. **Contradiction detection** (rule‑based first; LLM fallback).
8. **Structured clinical report** with recommendations + follow‑up timing.
9. **Alerting + Critical Mode** when red‑flags are detected.

**Critical Mode**: When severe visual cues are present, the UI simplifies to a single urgent alert with a direct physician‑referral CTA and disables non‑essential UI.

### Care Loop: Patient → Nurse → Specialist
- **Patient self‑reporting** via a shareable tokenized link (no login).
- **Nurse assessment** with BWAT score, trajectory, report, and clinical Q&A.
- **Physician referral** by one‑tap call/WhatsApp/email with pre‑filled urgency.

### Technical Stack
FastAPI + Next.js 14 PWA on a single **NVIDIA L4 (24GB)**. MedGemma runs in bfloat16; MedSigLIP can be CPU‑offloaded. The pipeline adapts to burns via burn‑specific labels and prompts.

---

## 3. Results and Impact
We validated the system end‑to‑end with **real model inference** on GCP (g2‑standard‑4). The submission emphasizes **BWAT‑grounded scoring** and **critical safety behaviors**.

### Qualitative Validation
- **Stable numeric outputs** from deterministic BWAT scoring.
- **High‑signal alerting** when red‑flag findings are present.
- **Interpretable trends** using BWAT totals + TIME composites across visits.

### Health Equity Impact
- **Democratizes expertise**: consistent wound assessment without specialist training.
- **Reduces variability**: same photo → same score across users.
- **Decision support**: clinical Q&A tied to the actual image and scores.
- **Earlier escalation**: critical cases are surfaced immediately.

### Limitations
- **Not a diagnosis**: requires clinical oversight and validation.
- **Latency**: full pipeline still takes tens of seconds.
- **Measurement gaps**: no true area/depth measurement yet.
- **Regulatory**: intended as clinical decision support (not autonomous care).

---

## Appendix — Historical LoRA Experiment (Not Used in Final Submission)
We previously fine‑tuned MedGemma 1.5 4B‑IT with LoRA to regress TIME scores (0–1). This improved agreement with teacher labels but introduced instability on out‑of‑distribution cases. For this submission we **disabled LoRA** and grounded scoring in BWAT with deterministic conversion.
