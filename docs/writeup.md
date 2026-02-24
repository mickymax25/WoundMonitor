oui# Wound Monitor — Objective Wound Trajectory Assessment with Three HAI‑DEF Models

### Project name
Wound Monitor — Objective Wound Trajectory Assessment

### Demo video
https://www.youtube.com/watch?v=yPOCyGpESkU

### Your team
- Michael HAYAT — Engineer & Data Science: product architecture, ML pipeline, backend, frontend.
- Delphine HAYAT-Hackoun — Cardiologist: clinical framing, validation lens, care pathway design.

### Problem statement
Chronic wounds (diabetic foot ulcers, pressure injuries, venous ulcers, burns) require frequent reassessment. Yet in practice, wound severity is still judged subjectively from visual inspection and narrative notes. Two clinicians can look at the same wound and disagree on whether it is improving or deteriorating. This inconsistency delays escalation, increases infection risk, and can ultimately lead to avoidable amputations and hospitalizations.

**Scale of the problem (commonly cited estimates):** 12M people live with chronic wounds worldwide; ~$28B annual treatment cost in the US; and up to 60% of complications could be prevented with earlier detection.

The TIME framework (Tissue, Inflammation/Infection, Moisture, Edge) improves communication but **does not provide a numeric, reproducible scale**. That means longitudinal tracking is still weak: improvement versus deterioration is often decided by “feel,” not a measurable trajectory. The highest‑impact opportunity is to turn a wound photo into a consistent numeric score that can be compared across visits and clinicians.

**User journey today:** a community nurse photographs a wound, writes a note, and makes a subjective call about severity. Escalation depends on that subjective judgment and may be delayed.

**User journey with Wound Monitor:** the patient can self‑report between visits via a tokenized link, the nurse runs a BWAT‑grounded assessment with a structured report, and the physician receives a one‑tap referral when critical findings are detected. This closed loop (patient → nurse → physician) enables faster escalation and more consistent care decisions across sites.

### Overall solution:
Wound Monitor is a **Progressive Web App (PWA)** that converts a wound photo into a **numeric, reproducible** severity score using the 13‑item **BWAT** scale (13–65), and derives **TIME composites** for intuitive trends. The system orchestrates **MedGemma (reasoning + structured observations), MedSigLIP (visual change), and MedASR (nurse dictation)**.

Key strengths aligned with HAI‑DEF usage:
- **MedGemma** produces structured BWAT observations (JSON) and generates clinical narrative and recommendations.
- **MedSigLIP** provides visual embeddings for change detection and supports stability when text is missing.
- **MedASR** transcribes nurse dictation, allowing hands‑free use in the field.

Clinical safety features:
- **Critical Mode** for red‑flag findings (necrosis, maggots, gross infection) that collapses the UI into an urgent alert and triggers immediate referral.
- **Contradiction detection** when nurse narrative conflicts with model‑derived trajectory, prompting review rather than silent disagreement.

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

**Architecture and stack**
- Backend: FastAPI + SQLite for rapid iteration and reproducible demos.
- Frontend: Next.js 14 PWA (installable on mobile, offline‑friendly cache).
- Models: MedGemma 1.5 4B‑IT (base), MedSigLIP 0.9B, MedASR 105M.
- Deployment: single NVIDIA L4 (24GB) on Google Cloud.

**Deployment and feasibility**
- Runs end‑to‑end on a single GPU instance, making it feasible for hospitals or regional deployments without heavy infrastructure.
- MedSigLIP can be CPU‑offloaded to reduce GPU memory pressure.
- BWAT scoring is deterministic once observations are extracted, improving stability across runs.
- Critical Mode allows safe escalation paths without relying on long narrative interpretation.

**Live testing**
We tested the system end‑to‑end with a live backend on Google Cloud (g2‑standard‑4, NVIDIA L4), demonstrating real model inference and complete UI workflow.

**Public code repository**
https://github.com/mickymax25/WoundMonitor

**Limitations**
- This is **clinical decision support**, not a diagnosis.
- Latency remains tens of seconds per full analysis.
- No true area/depth measurement yet (future segmentation and measurement planned).
- Regulatory clearance would be required for autonomous use.

---

## Appendix — Historical LoRA Experiment (Not Used in Final Submission)
We previously fine‑tuned MedGemma 1.5 4B‑IT with LoRA to regress TIME scores (0–1). This improved agreement with teacher labels but introduced instability on out‑of‑distribution cases. For this submission we **disabled LoRA** and grounded scoring in BWAT with deterministic conversion.
