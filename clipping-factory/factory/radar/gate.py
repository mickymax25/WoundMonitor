"""Gate G1 + scoring des campagnes (ARCHITECTURE.md §6).

G1 rejette automatiquement ce qui ne mérite pas de production :
budget entamé, CPM sous le seuil, catégories exclues, plateformes ou
exigences d'audience incompatibles. Le score classe ce qui passe —
la fraîcheur pèse lourd parce que les budgets s'épuisent en heures.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from ..config import RadarConfig
from ..models import Campaign, utcnow


@dataclass(frozen=True)
class GateResult:
    passed: bool
    reasons: list[str]      # motifs de rejet (vide si passed)
    score: float | None     # défini seulement si passed


def evaluate(c: Campaign, cfg: RadarConfig, now: datetime | None = None) -> GateResult:
    now = now or utcnow()
    reasons: list[str] = []

    if c.status != "active":
        reasons.append(f"statut={c.status}")

    # Catégories exclues (gambling/crypto/adulte…).
    text = c.searchable_text()
    hits = [kw for kw in cfg.excluded_keywords if kw in text]
    if hits:
        reasons.append(f"catégorie exclue: {', '.join(sorted(hits))}")

    # Budget restant.
    ratio = c.budget_remaining_ratio
    if ratio is not None and ratio < cfg.min_budget_remaining_ratio:
        reasons.append(
            f"budget restant {ratio:.0%} < {cfg.min_budget_remaining_ratio:.0%}"
        )

    # CPM minimal par devise. CPM inconnu = rejet (pas de production à l'aveugle).
    floor = cfg.min_cpm.get(c.currency)
    if c.cpm is None:
        reasons.append("CPM inconnu")
    elif floor is not None and c.cpm < floor:
        reasons.append(f"CPM {c.cpm} {c.currency} < seuil {floor}")

    # Au moins une plateforme servie par l'usine.
    if c.platforms and not set(p.lower() for p in c.platforms) & set(
        cfg.platforms_served
    ):
        reasons.append(f"plateformes non servies: {', '.join(c.platforms)}")

    # Exigences d'audience géo incompatibles.
    for country, share in c.audience_requirements.items():
        if (
            country.upper() not in cfg.audience_countries
            and share > cfg.max_foreign_audience_requirement
        ):
            reasons.append(f"exigence d'audience {country}≥{share:.0%} non servable")

    if reasons:
        return GateResult(passed=False, reasons=reasons, score=None)
    return GateResult(passed=True, reasons=[], score=score(c, cfg, now))


def score(c: Campaign, cfg: RadarConfig, now: datetime | None = None) -> float:
    """Score de priorité ∈ [0, 100] : fraîcheur 45 % · budget 30 % · CPM 25 %."""
    now = now or utcnow()

    age_h = max(0.0, (now - c.first_seen_at).total_seconds() / 3600.0)
    freshness = max(0.0, 1.0 - age_h / cfg.freshness_window_hours)

    ratio = c.budget_remaining_ratio
    budget = ratio if ratio is not None else 0.5  # inconnu = neutre

    floor = cfg.min_cpm.get(c.currency, 1.0) or 1.0
    # 1.0 au seuil, plafonné à 4x le seuil pour éviter qu'un CPM promo écrase tout.
    cpm_norm = min((c.cpm or 0.0) / floor, 4.0) / 4.0

    return round(100.0 * (0.45 * freshness + 0.30 * budget + 0.25 * cpm_norm), 1)
