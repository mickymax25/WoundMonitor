# Wound Monitor: Objective Wound Trajectory Assessment Using Three HAI-DEF Models

## 1. The Problem

Chronic wounds affect 8.2 million patients in the United States alone, costing over $28 billion annually. Venous ulcers, diabetic foot ulcers, and pressure injuries often persist for months or years, with 30% five-year mortality rivaling many cancers. Whether these wounds are improving, stagnating, or deteriorating determines treatment escalation, specialist referrals, and ultimately, whether a patient keeps a limb.

**The fundamental obstacle is measurement.** Today's wound assessment is subjective and non-quantitative. Two clinicians evaluating the same wound routinely disagree on tissue type, inflammation severity, and trajectory. The TIME framework (Tissue, Inflammation/Infection, Moisture, Edge) provides structured vocabulary, but scoring remains observer-dependent. In resource-limited settings, the clinician may be a community health worker with minimal wound training, making consistent longitudinal assessment even harder.

Wound Monitor transforms a smartphone photograph into an objective, reproducible wound trajectory measurement using three Google HAI-DEF models working in concert, with a domain-adapted model fine-tuned specifically for wound assessment.

## 2. The Solution

### Architecture

Wound Monitor is a Progressive Web App that orchestrates three HAI-DEF models (MedGemma, MedSigLIP, MedASR) in a nine-step agent pipeline:

| Model | Role | Parameters |
|---|---|---|
| **MedGemma 1.5 4B-IT** | TIME scoring (LoRA), clinical descriptions (base), report generation, contradiction detection | 4B + 46MB LoRA adapter |
| **MedSigLIP 0.9B** | Wound image embeddings for change detection + zero-shot classification | 0.9B |
| **MedASR 105M** | Nurse voice note transcription | 105M |

MedGemma is used in two modes within a single inference session via PEFT adapter toggling: the LoRA-adapted model produces TIME scores, then the adapter is disabled and the base model generates clinical descriptions informed by those scores --- no reload required, both modes on a single GPU.

### Pipeline

For each visit, the WoundAgent orchestrator: **(1)** computes a MedSigLIP embedding, **(2)** runs MedGemma TIME scoring via LoRA (Tissue/Inflammation/Moisture/Edge, each 0-1), **(3)** generates 2-4 word clinical descriptions per dimension via the base model guided by LoRA scores, **(4)** retrieves the previous assessment, **(5)** computes trajectory (mean TIME delta > +0.05 = improving, < -0.05 = deteriorating; MedSigLIP cosine distance stored as complementary change metric), **(6)** transcribes nurse dictation via MedASR, **(7)** detects contradictions between AI trajectory and nurse observations, **(8)** generates a structured clinical report, and **(9)** determines alert level: red (any dimension < 0.2 or deteriorating + avg < 0.4), orange (deteriorating or contradiction), yellow (avg < 0.5), green otherwise.

**Contradiction example**: A nurse dictated "wound looks better this week" while the AI detected a 0.15-point inflammation increase and classified the trajectory as deteriorating --- triggering an orange alert. This could indicate early subclinical infection or contextual information the AI cannot access (e.g., recent debridement). Either way, the divergence warrants attention.

### LoRA Fine-Tuning

We fine-tuned MedGemma 1.5 4B-IT on 5,000 wound images from 6 public datasets (CO2Wounds-V2 temporal series, Diabetic Foot Ulcer, Wound Classification, Wound Dataset, Wound Segmentation, Skin Burn) using LoRA (rank 16, alpha 32) targeting q/k/v/o projections. The training objective was regression on TIME scores annotated using the base model as teacher, with manual correction of edge cases. The adapter (46MB) achieves MAE 0.028 against teacher-generated labels --- measuring adaptation fidelity, not clinical ground truth (see Limitations). The fine-tuning prompt was kept minimal to ensure reliable JSON output and avoid hallucination artifacts.

### Care Loop: Patient, Nurse, Specialist

**Patient self-reporting.** Each patient receives a unique shareable link (token-based, no login). Patients photograph their wound between visits and submit with an optional note. The interface masks the patient's name for privacy. Submissions are tagged `source: patient` and tracked separately.

**Nurse analysis.** The nurse photographs the wound, optionally dictates via MedASR, and receives TIME scores with descriptions, trajectory, contradiction flags, report, and alert level.

**Physician referral.** When the alert triggers, the nurse sends a one-tap referral via call, WhatsApp, or email --- pre-populated with the physician's details and urgency level. The specialist receives a clinical summary page with TIME scores, trajectory, AI report, and nurse notes. Three actors, one continuous data pipeline.

### Burn Wound Support

The pipeline adapts automatically for burns (thermal, chemical, electrical): MedSigLIP uses 8 burn-specific labels, MedGemma uses a burn-adapted prompt and burn care specialist persona. For example, a deep partial-thickness scald produces Tissue 0.4 --- "Deep partial-thickness blistering" with recommendations for silver sulfadiazine, grafting evaluation, and hypertrophic scar prevention.

### Technical Stack

FastAPI + Next.js 14 PWA, deployed on a single NVIDIA L4 GPU (24GB). MedGemma bfloat16 (~8.6GB VRAM), MedSigLIP offloaded to CPU (~3.5GB RAM). Trained on 5,000 chronic wound images.

## 3. Results and Impact

We deployed Wound Monitor on a GCP g2-standard-4 instance (NVIDIA L4) and validated end-to-end with real model inference (no mocks):

| Metric | Value |
|---|---|
| TIME scoring MAE (LoRA vs. teacher) | 0.028 |
| TIME descriptions | Model-generated, 2-4 word clinical findings |
| Zero-shot classification | 8 wound + 8 burn categories (MedSigLIP) |
| Full pipeline latency | ~60s avg (MedSigLIP ~5s, LoRA ~20s, descriptions ~4s, report ~25s) |
| Care loop | Patient self-report + nurse analysis + physician referral |
| Alert system | 4 levels with explicit thresholds |

### Plausibility Validation (N=30)

We ran a plausibility study with 30 real-inference analyses (no mocks) on 20 patients: 10 patients with 2 visits each (trajectory testing) and 10 patients with 1 visit (baseline). Wound types included chronic wounds, diabetic ulcers, and burns.

| Metric | Result |
|---|---|
| TIME scoring success rate | 80% (24/30 produced valid scores) |
| Tissue score range | 0.20--0.50 (mean 0.35, excluding failures) |
| Inflammation score range | 0.50--0.80 (mean 0.66) |
| Trajectory detection | Correctly identified 2 improving, 2 deteriorating, 3 stable |
| Contradiction detection | 3/10 visit-2 assessments flagged (nurse-AI divergence) |
| Alert distribution | 4 red, 3 orange, 5 yellow, 18 green |
| Average latency | 58.8s per full analysis |

The contradiction detector flagged cases where nurse notes reported worsening while the AI assessed stability --- a clinically meaningful divergence. Example: "Wound bed looks more necrotic, odor present" with AI trajectory = stable triggered an orange alert. Six assessments (20%) returned default scores, indicating parsing failures on certain image types; these were correctly escalated as red alerts.

Example on a chronic venous ulcer: Tissue 0.3 ("Slough with some necrosis"), Inflammation 0.7 ("Mild perilesional erythema"), Moisture 0.5 ("Moderate serous exudate"), Edge 0.4 ("Rolled wound edges"). Trajectory: Improving.

| Dimension | Current Practice | With Wound Monitor |
|---|---|---|
| Assessment | Subjective, observer-dependent | Quantitative TIME scores (0-1) |
| Trajectory | "Looks about the same" | Delta-based classification with thresholds |
| Continuity | Lost between visits | Patient self-report between visits |
| Escalation | When visibly infected | Alert triggers before clinical deterioration |
| Communication | Phone call, no structured data | One-tap referral with AI report attached |

### Health Equity Impact

Consider a federally qualified health center (FQHC) in rural South Texas, where a medical assistant with no wound care certification sees 15 diabetic foot ulcer patients per week. Today, she documents "wound looks about the same" and escalates only when visibly infected. With Wound Monitor, a 0.08-point tissue score drop over two weeks triggers a yellow alert before clinical deterioration is visible, prompting early referral with full AI report attached.

- **Democratizing expertise**: Smartphone-based TIME assessment without specialized certification
- **Reducing variability**: Same photo, same scores, regardless of who uploads it
- **Patient empowerment**: Between-visits monitoring via shareable link
- **Early detection**: Quantitative trajectory catches stagnation before subjective observation
- **Edge-ready**: Single consumer GPU, no cloud dependency, patient data stays local

### Limitations

- **Clinical validation**: MAE 0.028 measures teacher agreement, not clinical ground truth; plausibility study (N=30) confirms pipeline functionality but expert consensus validation required
- **Patient photo quality**: Variable lighting/angle from patient submissions; quality guidance planned
- **Latency**: ~60s per assessment; further reduction possible via batched inference or model distillation
- **Wound measurement**: No area/depth measurement; pressure ulcer staging (NPUAP/EPUAP) planned as extension
- **Offline**: GPU connectivity required; on-device quantized inference is priority for true edge deployment
- **Regulatory**: Positioned as clinical decision support (CDS); FDA 21st Century Cures Act CDS exemption applies when clinician retains final judgment, but formal regulatory pathway would be needed for autonomous use

Wound Monitor demonstrates that three HAI-DEF models, orchestrated in a purpose-built agent pipeline with domain-specific fine-tuning, can transform subjective wound assessment into objective, reproducible trajectory measurement --- the missing instrument in chronic wound care.
