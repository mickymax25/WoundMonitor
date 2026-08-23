"""Station S7 — gate G3 : contrôle de conformité avant la file de validation.

Aucune exception manuelle (ARCHITECTURE.md §6) : un manquement = blocage.
Les règles viennent du dossier de recherche :
- crédit de la source obligatoire (condition de la citation, et de la
  plupart des briefs de campagne) ;
- campagne rémunérée → mention « Collaboration commerciale » (loi
  influenceurs 2023-451) ;
- persona IA → divulgation (AI Act art. 50 + règles TikTok) même quand le
  label TikTok n'est pas exigé (voix TTS générique) — on assume le persona ;
- musique : la source doit être déclarée sans musique (le fingerprint
  musical est la détection copyright la plus létale) ;
- durée dans les bornes plateforme/campagne.
"""

from __future__ import annotations

from dataclasses import dataclass

MIN_DURATION_S = 15.0
MAX_DURATION_S = 180.0
COMMERCIAL_BADGE = "Collaboration commerciale"
AI_BADGE = "Persona IA (voix de synthèse)"


@dataclass
class RenderMeta:
    duration_s: float
    credit_text: str
    badges: list[str]
    is_campaign: bool
    music_cleared: bool          # source déclarée sans musique (intro/outro coupés)
    authorization_kind: str      # 'campaign' | 'written' | 'native'


def check(meta: RenderMeta) -> list[str]:
    """Renvoie la liste des manquements. Vide = G3 passé."""
    issues: list[str] = []
    if not (MIN_DURATION_S <= meta.duration_s <= MAX_DURATION_S):
        issues.append(
            f"durée {meta.duration_s:.1f}s hors bornes"
            f" [{MIN_DURATION_S:.0f}–{MAX_DURATION_S:.0f}s]"
        )
    if not meta.credit_text.strip():
        issues.append("crédit source manquant")
    if meta.is_campaign and COMMERCIAL_BADGE not in meta.badges:
        issues.append(f"mention « {COMMERCIAL_BADGE} » manquante (loi influenceurs)")
    if AI_BADGE not in meta.badges:
        issues.append("divulgation du persona IA manquante")
    if not meta.music_cleared:
        issues.append("musique non vérifiée — couper intro/outro et confirmer")
    if meta.authorization_kind not in ("campaign", "written", "native"):
        issues.append(f"autorisation source invalide: {meta.authorization_kind}")
    return issues


def default_badges(is_campaign: bool) -> list[str]:
    badges = [AI_BADGE]
    if is_campaign:
        badges.insert(0, COMMERCIAL_BADGE)
    return badges
