"""Configuration de l'usine — seuils des quality gates et environnement.

Les valeurs par défaut viennent de RESEARCH.md / ARCHITECTURE.md (gate G1).
Tout est surchargeable par variable d'environnement pour ajuster sans redéployer.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None:
        return default
    try:
        return float(raw)
    except ValueError:
        return default


@dataclass(frozen=True)
class RadarConfig:
    # G1 : part minimale du budget encore disponible.
    min_budget_remaining_ratio: float = field(
        default_factory=lambda: _env_float("G1_MIN_BUDGET_RATIO", 0.60)
    )
    # G1 : CPM minimal par devise (par 1 000 vues).
    min_cpm: dict[str, float] = field(
        default_factory=lambda: {
            "USD": _env_float("G1_MIN_CPM_USD", 0.80),
            "EUR": _env_float("G1_MIN_CPM_EUR", 0.40),
        }
    )
    # G1 : catégories exclues (détectées par mots-clés dans nom/description/brief).
    excluded_keywords: tuple[str, ...] = (
        "casino", "gambling", "betting", "paris sportifs", "stake",
        "polymarket", "prediction market", "crypto", "trading signal",
        "forex", "adult", "onlyfans",
    )
    # Plateformes que l'usine sert (une campagne doit en accepter au moins une).
    platforms_served: tuple[str, ...] = ("tiktok", "instagram", "youtube")
    # Audiences que l'on peut servir de façon crédible ; une exigence géo
    # au-dessus de ce plafond sur un autre pays fait échouer G1.
    audience_countries: tuple[str, ...] = ("FR", "US", "GB", "CA", "BE", "CH")
    max_foreign_audience_requirement: float = field(
        default_factory=lambda: _env_float("G1_MAX_FOREIGN_AUDIENCE", 0.50)
    )
    # Fenêtre de fraîcheur pour le scoring (heures) — au-delà, le bonus tombe à 0.
    freshness_window_hours: float = field(
        default_factory=lambda: _env_float("RADAR_FRESHNESS_WINDOW_H", 48.0)
    )


@dataclass(frozen=True)
class Settings:
    db_path: str = field(
        default_factory=lambda: os.environ.get("FACTORY_DB", "factory.db")
    )
    whop_api_key: str | None = field(
        default_factory=lambda: os.environ.get("WHOP_API_KEY")
    )
    radar: RadarConfig = field(default_factory=RadarConfig)


def load_settings() -> Settings:
    return Settings()
