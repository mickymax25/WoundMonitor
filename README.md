# WoundChrono (Wound Monitor)

Objective wound trajectory assessment using three Google HAI‑DEF models (MedGemma, MedSigLIP, MedASR). The system produces BWAT‑grounded scores (13–65), derives TIME composites for trends, and triggers critical referral workflows on red‑flag findings.

## Architecture

- **MedGemma 1.5 4B‑IT (base)**: BWAT item observation extraction (JSON), report generation, contradiction detection, clinical Q&A
- **MedSigLIP**: image embeddings for change detection and zero‑shot visual hints
- **MedASR**: nurse voice note transcription

## Repo Layout

- `backend/` — FastAPI API + model orchestration
- `frontend/` — Next.js 14 PWA
- `docs/` — writeup + video script + finetuning report (historical)

## Quickstart (Local)

### Backend

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:3000`.

## Configuration (Environment)

All settings are loaded via `WOUNDCHRONO_` prefixed env vars (see `backend/app/config.py`). Common examples:

```bash
export WOUNDCHRONO_DATABASE_URL="sqlite:///./data/woundchrono.db"
export WOUNDCHRONO_MEDGEMMA_MODEL="google/medgemma-1.5-4b-it"
export WOUNDCHRONO_MEDGEMMA_LORA_PATH=""   # empty for base model
export WOUNDCHRONO_MEDSIGLIP_MODEL="google/medsiglip-448"
export WOUNDCHRONO_MEDASR_MODEL="google/medasr"
export WOUNDCHRONO_DEVICE="cuda"           # or "cpu"
```

## Notes

- Models are downloaded from HuggingFace on first run. Ensure you have access and have run `huggingface-cli login` if required.
- BWAT scoring is **clinical decision support** only and does not constitute a diagnosis.

## License

This repository is for hackathon use and demonstration purposes.
