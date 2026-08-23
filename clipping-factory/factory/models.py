"""Modèles de données du radar (station S0).

`Campaign` est la représentation normalisée d'une campagne de clipping,
quelle que soit la plateforme d'origine (Whop, Vyro, clip.farm, saisie
manuelle). Les adaptateurs de `factory.radar` produisent tous cet objet.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass
class Campaign:
    source: str                      # "whop" | "vyro" | "clipfarm" | "manual" | ...
    external_id: str                 # identifiant côté plateforme
    name: str
    url: str = ""
    description: str = ""
    currency: str = "USD"
    cpm: float | None = None         # rémunération par 1 000 vues
    budget_total: float | None = None
    budget_remaining: float | None = None
    min_payout: float | None = None
    max_per_video: float | None = None
    platforms: tuple[str, ...] = ()  # plateformes acceptées ("tiktok", ...)
    languages: tuple[str, ...] = ()  # langues du contenu attendu ("fr", "en")
    # Exigences d'audience géo, ex. {"US": 0.5} = "≥50 % d'audience US".
    audience_requirements: dict[str, float] = field(default_factory=dict)
    submission_window_hours: float | None = None
    status: str = "active"           # "active" | "exhausted" | "closed"
    first_seen_at: datetime = field(default_factory=utcnow)
    last_seen_at: datetime = field(default_factory=utcnow)

    @property
    def key(self) -> str:
        return f"{self.source}:{self.external_id}"

    @property
    def budget_remaining_ratio(self) -> float | None:
        if self.budget_total and self.budget_remaining is not None:
            if self.budget_total <= 0:
                return None
            return max(0.0, min(1.0, self.budget_remaining / self.budget_total))
        return None

    def searchable_text(self) -> str:
        return f"{self.name} {self.description}".lower()
