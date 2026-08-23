"""Interface des adaptateurs de sources de campagnes.

Chaque plateforme (Whop, Vyro, clip.farm, saisie manuelle…) implémente
`SourceAdapter.fetch()` et renvoie des `Campaign` normalisées. Le runner
ne connaît que cette interface — ajouter une plateforme = ajouter un fichier.
"""

from __future__ import annotations

from typing import Protocol

from ..models import Campaign


class SourceUnavailable(Exception):
    """La source ne peut pas être interrogée (clé absente, accès refusé…).

    Le runner l'enregistre comme avertissement, pas comme erreur fatale :
    une source indisponible ne bloque jamais le scan des autres.
    """


class SourceAdapter(Protocol):
    name: str

    def fetch(self) -> list[Campaign]:
        """Renvoie les campagnes actuellement visibles sur la source."""
        ...
