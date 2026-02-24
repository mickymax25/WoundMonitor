# Wound Monitor — Objective Wound Trajectory Assessment with Three HAI‑DEF Models

### Project name
Wound Monitor — Objective Wound Trajectory Assessment

### Demo video
https://www.youtube.com/watch?v=yPOCyGpESkU

### Your team
- Michael HAYAT — Engineer & Data Science: product architecture, ML pipeline, backend, frontend.
- Delphine HAYAT-Hackoun — Cardiologist: clinical framing, validation lens, care pathway design.

### Problem statement
Chronic wound care is a monitoring problem. Clinicians must decide whether a wound is improving, stable, or deteriorating — yet assessments remain subjective. Two clinicians can view the same wound and reach different conclusions, delaying escalation and increasing infection risk.

**Scale (sourced):** In the U.S. Medicare population, chronic wounds affect ~8.2M beneficiaries (~15%) and total wound‑related spending is estimated at $28.1–$96.8B annually. [1][2]

The TIME framework improves communication but **is not a numeric, reproducible scale**. Without a consistent score, longitudinal tracking is weak and early deterioration is often missed.

**User journey today:** patient photo + nurse note + subjective call → delayed escalation.  
**User journey with Wound Monitor:** patient self‑report between visits → nurse runs BWAT‑grounded assessment → physician receives one‑tap referral on critical findings. This closed loop (patient → nurse → physician) standardizes decisions across sites.

### Overall solution:
Wound Monitor is a **Progressive Web App (PWA)** that turns a wound photo into a **BWAT numeric score (13–65)** and a **trend over time**, with **TIME composites** for intuitive visualization. It orchestrates **MedGemma (reasoning + structured observations), MedSigLIP (visual change), and MedASR (nurse dictation)** to deliver a complete clinical workflow.

**HAI‑DEF model roles**
- **MedGemma**: extracts BWAT item observations (JSON), generates clinical report and recommendations.
- **MedSigLIP**: image embeddings for change detection and stability when text is missing.
- **MedASR**: hands‑free transcription of nurse dictation.

**Safety + escalation**
- **Critical Mode** for red‑flag findings (necrosis, maggots, gross infection) that collapses UI to a single urgent alert with direct referral.
- **Contradiction detection** when nurse narrative conflicts with model‑derived trajectory, prompting review.

### Technical details
**Pipeline (per visit)**
1. MedSigLIP embedding for visual change detection.
2. MedGemma observation extraction → BWAT item observations (JSON).
3. Deterministic BWAT scoring (13–65) with per‑item scores.
4. TIME composites derived from BWAT for trend UI only.
5. Previous visit retrieval and trajectory computation.
6. MedASR transcription of nurse dictation.
7. Contradiction detection (rule‑based first; LLM fallback).
8. Structured clinical report with recommendations and follow‑up timing.
9. Alerting + Critical Mode for red‑flags.

**Architecture and stack**
- Backend: FastAPI + SQLite (reproducible demo).
- Frontend: Next.js 14 PWA (installable on mobile).
- Models: MedGemma 1.5 4B‑IT (base), MedSigLIP 0.9B, MedASR 105M.
- Deployment: single NVIDIA L4 (24GB) on Google Cloud.

**Feasibility**
- Runs end‑to‑end on a single GPU instance; MedSigLIP can be CPU‑offloaded.
- BWAT scoring is deterministic once observations are extracted, reducing score drift.
- Conservative fallback: if structured extraction fails, the system falls back to vision signals and escalates.

**Live testing**
We tested the full workflow with a live backend on Google Cloud (g2‑standard‑4, NVIDIA L4).

**Public code repository**
https://github.com/mickymax25/WoundMonitor

**Limitations**
- Clinical decision support only (not a diagnosis).
- Latency remains tens of seconds per full analysis.
- No true area/depth measurement yet (segmentation planned).
- Regulatory clearance required for autonomous use.

---

## Sources
[1] Nussbaum et al., *Value in Health* (2018): Medicare chronic wounds prevalence and cost estimates. https://pubmed.ncbi.nlm.nih.gov/29304937/  
[2] Sen, *Advances in Wound Care* (2019): compendium summarizing Medicare wound burden. https://pmc.ncbi.nlm.nih.gov/articles/PMC6389759/

## Appendix — Historical LoRA Experiment (Not Used in Final Submission)
We previously fine‑tuned MedGemma 1.5 4B‑IT with LoRA to regress TIME scores (0–1). This improved agreement with teacher labels but introduced instability on out‑of‑distribution cases. For this submission we **disabled LoRA** and grounded scoring in BWAT with deterministic conversion.
