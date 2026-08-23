"""Adaptateur Whop Content Rewards.

Le listing public de Whop est une app JS : le chemin fiable est l'API
officielle, qui demande une clé (compte Whop → paramètres développeur,
variable d'environnement WHOP_API_KEY). Sans clé, l'adaptateur signale
proprement son indisponibilité au lieu de casser le scan.

NOTE : l'endpoint exact des campagnes Content Rewards est à confirmer sur
un compte réel (docs.whop.com évolue) — il est donc configurable via
WHOP_CAMPAIGNS_ENDPOINT. Le parsing (`parse_campaigns`) est indépendant du
transport et couvert par les tests sur fixture.
"""

from __future__ import annotations

import os

import httpx

from ..models import Campaign
from .base import SourceUnavailable

DEFAULT_ENDPOINT = "https://api.whop.com/api/v5/app/content_rewards/campaigns"


class WhopSource:
    name = "whop"

    def __init__(self, api_key: str | None = None, endpoint: str | None = None):
        self.api_key = api_key or os.environ.get("WHOP_API_KEY")
        self.endpoint = endpoint or os.environ.get(
            "WHOP_CAMPAIGNS_ENDPOINT", DEFAULT_ENDPOINT
        )

    def fetch(self) -> list[Campaign]:
        if not self.api_key:
            raise SourceUnavailable(
                "whop: WHOP_API_KEY absent — créer un compte Whop et définir la clé"
            )
        resp = httpx.get(
            self.endpoint,
            headers={"Authorization": f"Bearer {self.api_key}"},
            timeout=30,
        )
        if resp.status_code in (401, 403):
            raise SourceUnavailable(f"whop: accès refusé ({resp.status_code})")
        resp.raise_for_status()
        return parse_campaigns(resp.json())


def parse_campaigns(payload: dict | list) -> list[Campaign]:
    """Normalise la réponse Whop en `Campaign`.

    Tolérant aux variations de forme : liste brute ou objet {"data": [...]},
    champs en camelCase ou snake_case.
    """
    items = payload.get("data", payload) if isinstance(payload, dict) else payload
    out: list[Campaign] = []
    for item in items:
        get = item.get
        cpm = _first(get, "reward_rate", "rewardRate", "cpm")
        out.append(
            Campaign(
                source="whop",
                external_id=str(_first(get, "id", "campaign_id") or ""),
                name=str(_first(get, "title", "name") or "sans titre"),
                url=str(_first(get, "url", "route") or ""),
                description=str(_first(get, "description", "brief") or ""),
                currency=str(_first(get, "currency") or "USD").upper(),
                cpm=_num(cpm),
                budget_total=_num(_first(get, "total_budget", "totalBudget", "budget")),
                budget_remaining=_num(
                    _first(get, "budget_remaining", "remainingBudget", "budget_left")
                ),
                min_payout=_num(_first(get, "min_payout", "minimumPayout")),
                max_per_video=_num(_first(get, "max_payout", "maxPayoutPerVideo")),
                platforms=tuple(
                    str(p).lower() for p in (_first(get, "platforms") or [])
                ),
                languages=tuple(
                    str(lang).lower() for lang in (_first(get, "languages") or [])
                ),
                status=str(_first(get, "status") or "active").lower(),
            )
        )
    return [c for c in out if c.external_id]


def _first(get, *keys):
    for k in keys:
        v = get(k)
        if v is not None:
            return v
    return None


def _num(v) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None
