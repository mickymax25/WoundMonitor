"""Adaptateur « manual » — campagnes saisies à la main ou importées d'un JSON.

Utilisable dès le jour 1, avant toute clé API : quand on repère une campagne
(sur Whop, Discord, clip.farm…), on l'ajoute via `factory radar add` ou un
fichier JSON, et elle entre dans le même circuit G1 + scoring que le reste.
Format du fichier : une liste d'objets aux champs de `Campaign`
(source facultative, "manual" par défaut).
"""

from __future__ import annotations

import json
from pathlib import Path

from ..models import Campaign


class ManualSource:
    name = "manual"

    def __init__(self, path: str | Path | None = None):
        self.path = Path(path) if path else None

    def fetch(self) -> list[Campaign]:
        if self.path is None or not self.path.exists():
            return []
        raw = json.loads(self.path.read_text(encoding="utf-8"))
        return [parse_entry(entry) for entry in raw]


def parse_entry(entry: dict) -> Campaign:
    return Campaign(
        source=entry.get("source", "manual"),
        external_id=str(entry["external_id"]),
        name=entry["name"],
        url=entry.get("url", ""),
        description=entry.get("description", ""),
        currency=entry.get("currency", "USD"),
        cpm=entry.get("cpm"),
        budget_total=entry.get("budget_total"),
        budget_remaining=entry.get("budget_remaining"),
        min_payout=entry.get("min_payout"),
        max_per_video=entry.get("max_per_video"),
        platforms=tuple(entry.get("platforms", [])),
        languages=tuple(entry.get("languages", [])),
        audience_requirements=entry.get("audience_requirements", {}),
        submission_window_hours=entry.get("submission_window_hours"),
        status=entry.get("status", "active"),
    )
