# Wound Monitor — Objective Wound Trajectory Assessment with Three HAI‑DEF Models

### Project name
Wound Monitor — Objective Wound Trajectory Assessment

### Demo video
https://www.youtube.com/watch?v=yPOCyGpESkU

### Your team
- Michael HAYAT — Engineer & Data Science: product architecture, ML pipeline, backend, frontend.
- Delphine HAYAT-Hackoun — Docteur en Cardiologie: clinical framing, validation lens, care pathway design.

### Problem statement
Chronic wound care depends on knowing whether a wound is improving, stable, or deteriorating — yet assessments remain subjective. The TIME framework (Tissue, Inflammation/Infection, Moisture, Edge) improves communication but **is not a numeric, reproducible scale**. This leads to missed deterioration, delayed escalation, and avoidable complications. A reliable numeric trajectory is the missing instrument in wound care.

### Overall solution:
Wound Monitor is a **Progressive Web App (PWA)** that converts a wound photo into a **numeric, reproducible** severity score using the 13‑item **BWAT** scale (13–65) and derives **TIME composites** for intuitive trends. It orchestrates **MedGemma (reasoning + structured observations), MedSigLIP (visual change), and MedASR (nurse dictation)**. The system includes **Critical Mode** for red‑flag findings with one‑tap referral and **contradiction detection** when nurse narrative conflicts with model‑derived trajectory.

### Technical details
The system uses three HAI‑DEF models in a single pipeline:

1. **MedSigLIP embedding** for visual change detection.
2. **MedGemma observation extraction** → BWAT item observations (JSON).
3. **Deterministic BWAT scoring** (13–65) with per‑item scores.
4. **TIME composites** derived from BWAT (trend UI only).
5. **Previous visit retrieval** and trajectory computation.
6. **MedASR transcription** of nurse dictation.
7. **Contradiction detection** (rule‑based first; LLM fallback).
8. **Structured clinical report** with recommendations + follow‑up timing.
9. **Alerting + Critical Mode** for red‑flags (necrosis, maggots, gross infection).

**Deployment**: FastAPI + Next.js 14 PWA on a single **NVIDIA L4 (24GB)**. MedGemma runs in bfloat16; MedSigLIP can be CPU‑offloaded. We tested end‑to‑end with a live backend on Google Cloud (g2‑standard‑4, NVIDIA L4).

**Care loop**: patient self‑report via tokenized link → nurse assessment → one‑tap physician referral.

**Public code repository**: https://github.com/mickymax25/WoundMonitor

**Limitations**: not a diagnosis; latency still tens of seconds; no true area/depth measurement yet; intended as clinical decision support.

---

## Appendix — Historical LoRA Experiment (Not Used in Final Submission)
We previously fine‑tuned MedGemma 1.5 4B‑IT with LoRA to regress TIME scores (0–1). This improved agreement with teacher labels but introduced instability on out‑of‑distribution cases. For this submission we **disabled LoRA** and grounded scoring in BWAT with deterministic conversion.
