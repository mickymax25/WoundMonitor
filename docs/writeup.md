# WoundChrono: Objective Wound Trajectory Assessment Using Three HAI-DEF Models

## 1. The Problem

Chronic wounds affect 8.2 million patients in the United States alone, costing the healthcare system over $28 billion annually. Venous ulcers, diabetic foot ulcers, and pressure injuries often persist for months or years, with 30% five-year mortality rivaling many cancers. The clinical trajectory of these wounds --- whether they are improving, stagnating, or deteriorating --- determines treatment escalation, specialist referrals, and ultimately, whether a patient keeps a limb.

**The fundamental obstacle is measurement.** Today's wound assessment is subjective, inconsistent, and non-quantitative. Two clinicians evaluating the same wound on the same day routinely disagree on tissue type, inflammation severity, and healing trajectory. The TIME framework (Tissue, Inflammation/Infection, Moisture, Edge) provides a structured vocabulary, but scoring remains observer-dependent. In resource-limited settings --- community health centers, home care, rural clinics --- the clinician may be a community health worker with minimal wound care training, making consistent longitudinal assessment even harder.

**The consequences are preventable.** A wound that stagnates for two weeks without detection continues accumulating biofilm. A trajectory reversal missed between visits becomes a hospital admission. The gap between what clinicians observe and what they document creates a blind spot in the care record that propagates through every downstream decision.

WoundChrono addresses this gap: it transforms a smartphone photograph into an objective, reproducible wound trajectory measurement using three Google HAI-DEF models working in concert.

## 2. The Solution

### Architecture

WoundChrono is a Progressive Web App designed for the workflow of a wound care nurse: photograph the wound, optionally dictate observations, receive an objective assessment in under 30 seconds. The system uses three HAI-DEF models in an eight-step analysis pipeline:

| Model | Role | Parameters |
|---|---|---|
| **MedGemma 1.5 4B-IT** | TIME classification + clinical report generation + contradiction detection | 4B |
| **MedSigLIP 0.9B** | Wound image embeddings for change detection + zero-shot classification | 0.9B |
| **MedASR** | Nurse voice note transcription | 105M |

The pipeline orchestrator (WoundAgent) executes the following steps for each visit:

1. **MedSigLIP embedding**: Compute a 768-dimensional image embedding capturing wound morphology
2. **MedGemma TIME classification**: Structured scoring of Tissue (0-1), Inflammation (0-1), Moisture (0-1), Edge advancement (0-1) via vision-language prompting
3. **Previous assessment retrieval**: Query the patient's last analyzed visit from the database
4. **Trajectory computation**: Compare current TIME scores and cosine distance between embeddings to classify trajectory as improving, stable, or deteriorating
5. **Audio transcription** (optional): MedASR transcribes nurse dictation into structured text
6. **Contradiction detection**: MedGemma compares the AI-determined trajectory against nurse observations, flagging discrepancies (e.g., nurse says "improving" while AI detects deterioration)
7. **Report generation**: MedGemma produces a structured clinical summary with current status, change since last visit, recommended interventions, and follow-up timeline
8. **Alert determination**: Rules engine maps trajectory + TIME scores + contradictions to a four-level alert system (green/yellow/orange/red)

### Why Three Models Together

No single model solves wound trajectory assessment. MedGemma excels at structured clinical reasoning from images but produces different embeddings for semantically similar inputs --- it is a generative model, not an embedding model. MedSigLIP produces consistent, comparable embeddings in a shared vision-language space, enabling reliable change detection across visits. MedASR bridges the gap between what the AI sees and what the clinician observes, enabling contradiction detection that neither modality achieves alone.

The contradiction detection feature is clinically significant: when AI assessment and clinician observation diverge, it signals either a subtle finding the clinician missed or contextual information the AI cannot access (e.g., recent medication change, patient non-compliance). Either way, the divergence warrants attention.

### Technical Stack

- **Backend**: FastAPI + SQLite, Python 3.10, PyTorch, Transformers 5.1
- **Frontend**: Next.js 14 PWA with camera/microphone capture via Web APIs
- **Deployment**: Single NVIDIA L4 GPU (24GB), total model footprint ~12.5GB VRAM
- **Data**: CO2Wounds-V2 dataset (764 chronic wound images with temporal series)

## 3. Results and Impact

### Demo Validation

We deployed WoundChrono on a cloud GPU instance and analyzed three simulated patients with 11 wound assessments from the CO2Wounds-V2 dataset:

| Patient | Wound Type | Visits | Detected Trajectory | Alert |
|---|---|---|---|---|
| Maria G. | Venous ulcer | 4 | Stable | Green |
| Carlos R. | Diabetic ulcer | 3 | Stable | Green |
| Rosa T. | Pressure ulcer | 4 | Deteriorating | Orange |

Rosa T.'s deterioration was correctly detected through declining inflammation scores (1.0 to 0.7) between visits 3 and 4, triggering an orange alert. This is the type of trajectory change that, in clinical practice, would prompt care plan escalation.

**Latency**: Full 8-step analysis completes in under 30 seconds on a single L4 GPU, compatible with clinical workflow where the nurse photographs during dressing change.

### Health Equity Impact

WoundChrono directly addresses health equity in wound care:

- **Democratizing expertise**: A community health worker with a smartphone can obtain TIME-framework-quality assessment previously requiring specialized wound care certification
- **Reducing inter-observer variability**: The same wound photograph produces the same scores regardless of who uploads it, eliminating the assessment lottery that disadvantages patients in under-resourced settings
- **Enabling remote supervision**: The structured reports and alert system allow a wound care specialist to remotely oversee dozens of patients, extending expertise to rural and underserved areas
- **Early deterioration detection**: The quantitative trajectory tracking detects stagnation and deterioration earlier than subjective observation, potentially preventing hospitalizations and amputations

### Limitations and Future Work

- **Validation scope**: TIME scores have not been validated against expert consensus panels; the current outputs reflect MedGemma's clinical reasoning, which requires formal clinical validation
- **Dataset constraints**: CO2Wounds-V2 primarily contains leprosy-associated wounds; generalization to diabetic and venous ulcers needs broader training data
- **Wound measurement**: The current system assesses qualitative characteristics (tissue type, inflammation) but does not measure wound area or depth, which are important trajectory indicators
- **Offline capability**: The PWA caches static assets but requires network connectivity for analysis; a future version could run quantized models on-device

WoundChrono demonstrates that three HAI-DEF models, orchestrated in a purpose-built pipeline, can transform subjective wound assessment into objective, reproducible trajectory measurement --- the missing instrument in chronic wound care.
