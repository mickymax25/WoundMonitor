"""Accès LLM de l'usine — deux transports, mêmes interfaces.

- Chemin direct Anthropic (SDK `anthropic`, sorties structurées natives) :
  `ANTHROPIC_API_KEY`.
- Chemin OpenRouter (API compatible OpenAI, un seul compte pour tous les
  modèles) : `OPENROUTER_API_KEY`, modèle via `OPENROUTER_MODEL`
  (défaut : anthropic/claude-opus-5 — slugs sur openrouter.ai/models).

`pick_scorer()` / `pick_writer()` choisissent automatiquement : Anthropic
si sa clé est là, sinon OpenRouter, sinon erreur explicite.
"""

from __future__ import annotations

import json
import os

import httpx

OPENROUTER_ENDPOINT = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_OPENROUTER_MODEL = "anthropic/claude-opus-5"


class LLMUnavailable(Exception):
    pass


class OpenRouterClient:
    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        transport: httpx.BaseTransport | None = None,
    ):
        self.api_key = api_key or os.environ.get("OPENROUTER_API_KEY")
        self.model = model or os.environ.get(
            "OPENROUTER_MODEL", DEFAULT_OPENROUTER_MODEL
        )
        self._transport = transport

    def complete_json(
        self, system: str, user: str, schema: dict, max_tokens: int = 16000
    ) -> dict:
        """Une complétion contrainte par un JSON Schema ; renvoie l'objet parsé."""
        if not self.api_key:
            raise LLMUnavailable("OPENROUTER_API_KEY absent")
        with httpx.Client(transport=self._transport, timeout=300) as client:
            resp = client.post(
                OPENROUTER_ENDPOINT,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "X-Title": "Usine a Clips",
                },
                json={
                    "model": self.model,
                    "max_tokens": max_tokens,
                    "messages": [
                        {"role": "system", "content": system},
                        {"role": "user", "content": user},
                    ],
                    "response_format": {
                        "type": "json_schema",
                        "json_schema": {
                            "name": "output",
                            "strict": True,
                            "schema": schema,
                        },
                    },
                },
            )
        resp.raise_for_status()
        payload = resp.json()
        try:
            content = payload["choices"][0]["message"]["content"]
            return json.loads(content)
        except (KeyError, IndexError, TypeError, json.JSONDecodeError) as exc:
            raise LLMUnavailable(
                f"réponse OpenRouter inexploitable ({self.model}): {exc}"
            ) from exc


def anthropic_available() -> bool:
    return bool(os.environ.get("ANTHROPIC_API_KEY"))


def openrouter_available() -> bool:
    return bool(os.environ.get("OPENROUTER_API_KEY"))


def pick_scorer():
    from .moments import ClaudeScorer, OpenRouterScorer

    if anthropic_available():
        return ClaudeScorer()
    if openrouter_available():
        return OpenRouterScorer()
    raise LLMUnavailable(
        "aucune clé LLM — définir ANTHROPIC_API_KEY ou OPENROUTER_API_KEY"
    )


def pick_writer():
    from .reaction import ClaudeReactionWriter, OpenRouterReactionWriter

    if anthropic_available():
        return ClaudeReactionWriter()
    if openrouter_available():
        return OpenRouterReactionWriter()
    raise LLMUnavailable(
        "aucune clé LLM — définir ANTHROPIC_API_KEY ou OPENROUTER_API_KEY"
    )
