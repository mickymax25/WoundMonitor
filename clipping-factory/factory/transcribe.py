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


_OPENROUTER_AUDIO_PROMPT = """\
Transcris fidèlement cet extrait audio, dans la langue parlée.
Découpe en segments de 3 à 10 secondes alignés sur les phrases.
Les timestamps start/end sont en secondes, RELATIFS AU DÉBUT DE CE FICHIER
AUDIO (qui est un morceau d'un épisode plus long). N'invente rien : si un
passage est inaudible, saute-le."""

_SEGMENTS_SCHEMA = {
    "type": "object",
    "properties": {
        "segments": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "start": {"type": "number"},
                    "end": {"type": "number"},
                    "text": {"type": "string"},
                },
                "required": ["start", "end", "text"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["segments"],
    "additionalProperties": False,
}


class OpenRouterTranscriber:
    """Transcription via un modèle multimodal audio d'OpenRouter (Gemini…).

    Permet de tout faire avec une seule clé (OPENROUTER_API_KEY). Précision
    des timestamps inférieure à Whisper — les tranches courtes (5 min par
    défaut) bornent la dérive ; Groq/Whisper reste le chemin de précision.
    Modèle via OPENROUTER_AUDIO_MODEL (défaut : google/gemini-3.7-flash).
    """

    def __init__(self, client=None, model: str | None = None, chunk_s: int = 300):
        from .llm import OpenRouterClient

        self.client = client or OpenRouterClient(
            model=model
            or os.environ.get("OPENROUTER_AUDIO_MODEL", "google/gemini-3.7-flash")
        )
        self.name = f"openrouter:{self.client.model}"
        self.chunk_s = chunk_s

    def transcribe(self, audio_path: Path) -> list[Segment]:
        import base64

        segments: list[Segment] = []
        for chunk_path, offset in self._split(audio_path):
            b64 = base64.b64encode(chunk_path.read_bytes()).decode()
            data = self.client.complete_json(
                system=_OPENROUTER_AUDIO_PROMPT,
                user=[
                    {"type": "text",
                     "text": "Transcris ce fichier audio en segments horodatés."},
                    {"type": "input_audio",
                     "input_audio": {"data": b64, "format": "mp3"}},
                ],
                schema=_SEGMENTS_SCHEMA,
                max_tokens=32000,
            )
            for s in data.get("segments", []):
                text = str(s["text"]).strip()
                if text:
                    segments.append(Segment(
                        start=offset + float(s["start"]),
                        end=offset + float(s["end"]),
                        text=text,
                    ))
        segments.sort(key=lambda s: s.start)
        return segments

    def _split(self, audio_path: Path) -> list[tuple[Path, float]]:
        """Découpe en tranches mp3 mono 32 kbps ; renvoie (chemin, offset réel)."""
        import subprocess

        outdir = audio_path.parent / f"{audio_path.stem}-chunks"
        outdir.mkdir(parents=True, exist_ok=True)
        pattern = outdir / "chunk-%03d.mp3"
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", "-i", str(audio_path),
             "-ac", "1", "-b:a", "32k", "-f", "segment",
             "-segment_time", str(self.chunk_s), str(pattern)],
            check=True,
        )
        chunks = sorted(outdir.glob("chunk-*.mp3"))
        out, offset = [], 0.0
        for chunk in chunks:
            if chunk.stat().st_size < 2048:  # tranche résiduelle vide
                continue
            probe = subprocess.run(
                ["ffprobe", "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=noprint_wrappers=1:nokey=1", str(chunk)],
                capture_output=True, text=True,
            )
            try:
                duration = float(probe.stdout.strip())
            except ValueError:
                continue  # tranche illisible — on ne bloque pas la chaîne
            if duration >= 1.0:
                out.append((chunk, offset))
            offset += duration
        return out


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
