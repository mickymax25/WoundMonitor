"""Voix du persona — synthèse TTS derrière une interface d'adaptateurs.

Règle du dossier (RESEARCH.md §4) : voix GÉNÉRIQUE, jamais un clone d'une
personne réelle — c'est ce qui dispense du label IA TikTok et écarte
l'art. 226-8 du Code pénal. Adaptateurs :

- ElevenLabsTTS : qualité de référence FR/EN (ELEVENLABS_API_KEY,
  ELEVENLABS_VOICE_ID — choisir une voix de la banque, pas un clone).
- FixtureTTS : bip de durée proportionnelle au texte via ffmpeg — tests et
  rejeu sans réseau. Cartesia s'ajoutera ici (même interface).
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Protocol

import httpx


class TTSUnavailable(Exception):
    pass


class TTS(Protocol):
    name: str

    def synth(self, text: str, language: str, out_path: Path) -> Path: ...


class ElevenLabsTTS:
    name = "elevenlabs"

    def __init__(self, api_key: str | None = None, voice_id: str | None = None):
        self.api_key = api_key or os.environ.get("ELEVENLABS_API_KEY")
        self.voice_id = voice_id or os.environ.get("ELEVENLABS_VOICE_ID")

    def synth(self, text: str, language: str, out_path: Path) -> Path:
        if not self.api_key or not self.voice_id:
            raise TTSUnavailable(
                "ELEVENLABS_API_KEY / ELEVENLABS_VOICE_ID absents — choisir une "
                "voix générique de la banque ElevenLabs (jamais un clone)"
            )
        resp = httpx.post(
            f"https://api.elevenlabs.io/v1/text-to-speech/{self.voice_id}",
            headers={"xi-api-key": self.api_key},
            json={
                "text": text,
                "model_id": "eleven_multilingual_v2",
                "output_format": "mp3_44100_128",
            },
            timeout=120,
        )
        resp.raise_for_status()
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_bytes(resp.content)
        return out_path


class FixtureTTS:
    """Signal audio synthétique ~2,5 mots/seconde — tests hors ligne."""

    name = "fixture"

    def synth(self, text: str, language: str, out_path: Path) -> Path:
        duration = max(1.0, len(text.split()) / 2.5)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(
            [
                "ffmpeg", "-y", "-loglevel", "error",
                "-f", "lavfi", "-i", f"sine=frequency=440:duration={duration:.2f}",
                "-ar", "44100", "-ac", "2", str(out_path),
            ],
            check=True,
        )
        return out_path
