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


class OpenRouterTTS:
    """Voix OpenAI (gpt-audio) via OpenRouter — une seule clé pour tout.

    Modèle via OPENROUTER_TTS_MODEL (défaut openai/gpt-audio-mini), voix via
    FACTORY_TTS_VOICE (alloy, ash, coral, sage, verse… — voix génériques
    OpenAI : conformes à la règle « jamais un clone d'une personne réelle »).
    """

    def __init__(self, client=None, model: str | None = None,
                 voice: str | None = None):
        from .llm import OpenRouterClient

        self.client = client or OpenRouterClient(
            model=model or os.environ.get("OPENROUTER_TTS_MODEL",
                                          "openai/gpt-audio-mini")
        )
        self.voice = voice or os.environ.get("FACTORY_TTS_VOICE", "ash")
        self.name = f"openrouter:{self.client.model}:{self.voice}"

    def synth(self, text: str, language: str, out_path: Path) -> Path:
        # La sortie audio de gpt-audio exige stream=true, et le streaming
        # n'accepte que le PCM brut (pcm16, 24 kHz mono) — on collecte les
        # deltas base64 puis on convertit en WAV standard via ffmpeg.
        import base64
        import json

        import httpx

        from .llm import OPENROUTER_ENDPOINT

        if not self.client.api_key:
            raise TTSUnavailable("OPENROUTER_API_KEY absent")
        body = {
            "model": self.client.model,
            "modalities": ["text", "audio"],
            "audio": {"voice": self.voice, "format": "pcm16"},
            "stream": True,
            "messages": [
                {"role": "system",
                 "content": "Tu es un comédien de doublage. Lis EXACTEMENT le "
                            "texte fourni par l'utilisateur, sans rien ajouter "
                            f"ni commenter. Langue : {language}. Ton énergique "
                            "et complice de commentateur de vidéos courtes, "
                            "débit naturel légèrement rapide."},
                {"role": "user", "content": text},
            ],
        }
        last = "?"
        for attempt in range(3):
            if attempt:
                import time

                time.sleep(2 ** attempt)
            pcm = bytearray()
            try:
                with httpx.stream(
                    "POST", OPENROUTER_ENDPOINT,
                    headers={"Authorization": f"Bearer {self.client.api_key}",
                             "X-Title": "Usine a Clips"},
                    json=body, timeout=300,
                ) as resp:
                    if resp.status_code == 429 or resp.status_code >= 500:
                        last = f"HTTP {resp.status_code}"
                        continue
                    if resp.status_code != 200:
                        resp.read()
                        last = resp.text[:200]
                        continue
                    for line in resp.iter_lines():
                        if not line.startswith("data: ") or line == "data: [DONE]":
                            continue
                        try:
                            delta = json.loads(line[6:])["choices"][0].get("delta", {})
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue
                        audio = delta.get("audio")
                        if audio and audio.get("data"):
                            pcm += base64.b64decode(audio["data"])
            except httpx.HTTPError as exc:  # proxy/réseau transitoire
                last = f"réseau: {exc}"
                continue
            if len(pcm) < 4800:  # < 0,1 s : réponse vide
                last = "flux audio vide"
                continue
            out_path.parent.mkdir(parents=True, exist_ok=True)
            raw = out_path.with_suffix(".pcm")
            raw.write_bytes(bytes(pcm))
            subprocess.run(
                ["ffmpeg", "-y", "-loglevel", "error",
                 "-f", "s16le", "-ar", "24000", "-ac", "1", "-i", str(raw),
                 "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le", str(out_path)],
                check=True,
            )
            raw.unlink(missing_ok=True)
            return out_path
        raise TTSUnavailable(
            f"TTS OpenRouter en échec après 3 tentatives ({self.client.model}): {last}"
        )


def pick_tts():
    """ElevenLabs si sa clé est là, sinon la voix OpenAI via OpenRouter."""
    if os.environ.get("ELEVENLABS_API_KEY") and os.environ.get("ELEVENLABS_VOICE_ID"):
        return ElevenLabsTTS()
    if os.environ.get("OPENROUTER_API_KEY"):
        return OpenRouterTTS()
    raise TTSUnavailable(
        "aucune voix disponible — définir OPENROUTER_API_KEY ou"
        " ELEVENLABS_API_KEY/ELEVENLABS_VOICE_ID"
    )


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
