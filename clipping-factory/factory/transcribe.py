"""Station S2 — transcription horodatée (FR/EN).

Le transcript est la matière première de S3 : une liste de segments
{start, end, text}, stockée en JSON à côté de l'audio. Adaptateurs :

- GroqTranscriber : Whisper large-v3-turbo via l'API Groq (~0,04 $/h audio,
  le choix coût/qualité de RESEARCH.md §5.2). Nécessite GROQ_API_KEY.
- FixtureTranscriber : transcript pré-calculé (tests, rejeu hors ligne).

L'interface est la même : `transcribe(audio_path) -> list[Segment]`, donc un
backend local (faster-whisper sur GPU) se branchera sans toucher au reste.
"""

from __future__ import annotations

import json
import os
import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Protocol

import httpx

GROQ_ENDPOINT = "https://api.groq.com/openai/v1/audio/transcriptions"
GROQ_MODEL = os.environ.get("GROQ_WHISPER_MODEL", "whisper-large-v3-turbo")


@dataclass
class Segment:
    start: float
    end: float
    text: str


class Transcriber(Protocol):
    name: str

    def transcribe(self, audio_path: Path) -> list[Segment]: ...


class TranscriberUnavailable(Exception):
    pass


class GroqTranscriber:
    name = "groq-whisper"

    def __init__(self, api_key: str | None = None):
        self.api_key = api_key or os.environ.get("GROQ_API_KEY")

    def transcribe(self, audio_path: Path) -> list[Segment]:
        if not self.api_key:
            raise TranscriberUnavailable(
                "GROQ_API_KEY absent — créer une clé sur console.groq.com"
            )
        with open(audio_path, "rb") as fh:
            resp = httpx.post(
                GROQ_ENDPOINT,
                headers={"Authorization": f"Bearer {self.api_key}"},
                data={"model": GROQ_MODEL, "response_format": "verbose_json"},
                files={"file": (audio_path.name, fh)},
                timeout=600,
            )
        resp.raise_for_status()
        payload = resp.json()
        return [
            Segment(start=float(s["start"]), end=float(s["end"]), text=s["text"].strip())
            for s in payload.get("segments", [])
        ]


class FixtureTranscriber:
    """Transcript fourni d'avance — tests et rejeu sans réseau."""

    name = "fixture"

    def __init__(self, segments: list[Segment]):
        self.segments = segments

    def transcribe(self, audio_path: Path) -> list[Segment]:
        return self.segments


def save_transcript(segments: list[Segment], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps([asdict(s) for s in segments], ensure_ascii=False), encoding="utf-8"
    )


def load_transcript(path: Path) -> list[Segment]:
    return [Segment(**s) for s in json.loads(path.read_text(encoding="utf-8"))]


def transcribe_episode(
    conn: sqlite3.Connection,
    episode_id: int,
    transcriber: Transcriber,
    media_dir: str | Path,
) -> Path:
    """Transcrit un épisode 'fetched' → statut 'transcribed'."""
    row = conn.execute("SELECT * FROM episodes WHERE id=?", (episode_id,)).fetchone()
    if row is None:
        raise ValueError(f"épisode {episode_id} inconnu")
    if not row["audio_path"]:
        raise ValueError(f"épisode {episode_id}: audio non téléchargé (statut {row['status']})")

    segments = transcriber.transcribe(Path(row["audio_path"]))
    path = Path(media_dir) / f"episode-{episode_id}.transcript.json"
    save_transcript(segments, path)
    conn.execute(
        "UPDATE episodes SET status='transcribed', transcript_path=? WHERE id=?",
        (str(path), episode_id),
    )
    conn.commit()
    return path
