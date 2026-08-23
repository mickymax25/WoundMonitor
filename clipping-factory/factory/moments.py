"""Station S3 — détection des moments forts (le maillon différenciant).

Deux scorers derrière la même interface :

- HeuristicScorer : marqueurs lexicaux FR/EN (hook, émotion, autonomie du
  segment), zéro API. Sert de baseline, de mode dégradé et de filtre
  pré-LLM quand on voudra réduire les coûts.
- ClaudeScorer : LLM avec sorties structurées — lit tout le transcript
  horodaté et renvoie les meilleures fenêtres 20–60 s avec scores et
  justification.

Le gate G2 (ARCHITECTURE.md §6) s'applique au score composite /10 :
seuls les moments ≥ seuil partent vers l'écriture de la réaction (S4).
"""

from __future__ import annotations

import os
import re
import sqlite3
from dataclasses import dataclass
from typing import Protocol

from .models import utcnow
from .transcribe import Segment

MIN_LEN_S = 20.0
MAX_LEN_S = 60.0
HARD_MAX_LEN_S = 90.0


@dataclass
class MomentCandidate:
    t_start: float
    t_end: float
    title: str
    hook: float          # /10
    emotion: float       # /10
    autonomy: float      # /10
    justification: str

    @property
    def score(self) -> float:
        return round(0.4 * self.hook + 0.3 * self.emotion + 0.3 * self.autonomy, 2)


class MomentScorer(Protocol):
    name: str

    def find_moments(
        self, segments: list[Segment], language: str, top_n: int = 5
    ) -> list[MomentCandidate]: ...


# ---------------------------------------------------------------------------
# Scorer heuristique (baseline sans API)
# ---------------------------------------------------------------------------

_HOOK_MARKERS = {
    "fr": (
        "personne ne", "la vérité", "je vais te dire", "tu sais pourquoi",
        "le secret", "incroyable", "jamais", "tout le monde pense",
        "ce que personne", "attention", "la plus grosse erreur",
    ),
    "en": (
        "nobody", "the truth", "let me tell you", "the secret", "never",
        "everyone thinks", "insane", "crazy", "the biggest mistake",
        "you won't believe", "here's why",
    ),
}
_EMOTION_MARKERS = {
    "fr": ("(rires)", "c'est fou", "énorme", "vraiment", "franchement",
           "totalement", "hallucinant", "choqué"),
    "en": ("[laughs]", "(laughs)", "literally", "absolutely", "unbelievable",
           "shocking", "wild", "no way"),
}
_WEAK_OPENERS = {
    "fr": ("donc", "et puis", "du coup", "parce que", "mais bon", "voilà",
           "après", "en fait donc"),
    "en": ("so", "and then", "because", "but yeah", "anyway", "also"),
}


class HeuristicScorer:
    name = "heuristic"

    def find_moments(
        self, segments: list[Segment], language: str, top_n: int = 5
    ) -> list[MomentCandidate]:
        lang = "fr" if language.startswith("fr") else "en"
        candidates = [
            self._score_window(w, lang) for w in _windows(segments)
        ]
        candidates.sort(key=lambda c: c.score, reverse=True)
        return _drop_overlaps(candidates)[:top_n]

    def _score_window(self, window: list[Segment], lang: str) -> MomentCandidate:
        text = " ".join(s.text for s in window)
        lower = text.lower()
        first = window[0].text.strip().lower()

        hook = 3.0
        hook += 2.0 * min(2, sum(m in lower[:160] for m in _HOOK_MARKERS[lang]))
        if "?" in window[0].text:
            hook += 2.0
        if re.search(r"\b\d[\d  ]*(%|€|\$|ans?|millions?|milliards?|k\b)", lower):
            hook += 1.0

        emotion = 3.0
        emotion += 1.5 * min(3, sum(m in lower for m in _EMOTION_MARKERS[lang]))
        emotion += min(2.0, text.count("!") * 1.0)

        autonomy = 6.0
        if any(first.startswith(op) for op in _WEAK_OPENERS[lang]):
            autonomy -= 3.0
        if window[-1].text.strip().endswith((".", "!", "?", "…")):
            autonomy += 2.0
        if len(text.split()) < 30:
            autonomy -= 2.0

        clamp = lambda v: max(0.0, min(10.0, v))
        return MomentCandidate(
            t_start=window[0].start,
            t_end=window[-1].end,
            title=window[0].text.strip()[:80],
            hook=clamp(hook),
            emotion=clamp(emotion),
            autonomy=clamp(autonomy),
            justification="scoring heuristique (marqueurs lexicaux)",
        )


def _windows(segments: list[Segment]) -> list[list[Segment]]:
    """Fenêtres candidates 20–60 s alignées sur les segments, pas ~½ fenêtre."""
    out: list[list[Segment]] = []
    i = 0
    while i < len(segments):
        window = [segments[i]]
        j = i + 1
        while j < len(segments) and (segments[j].end - window[0].start) <= MAX_LEN_S:
            window.append(segments[j])
            j += 1
        if (window[-1].end - window[0].start) >= MIN_LEN_S:
            out.append(window)
        # avance d'environ une demi-fenêtre
        advanced = i
        while (
            advanced < len(segments) - 1
            and segments[advanced].start - segments[i].start < MAX_LEN_S / 2
        ):
            advanced += 1
        i = max(advanced, i + 1)
    return out


def _drop_overlaps(cands: list[MomentCandidate]) -> list[MomentCandidate]:
    kept: list[MomentCandidate] = []
    for c in cands:
        if all(
            c.t_start >= k.t_end or c.t_end <= k.t_start for k in kept
        ):
            kept.append(c)
    return kept


# ---------------------------------------------------------------------------
# Scorer LLM (sorties structurées)
# ---------------------------------------------------------------------------

DEFAULT_LLM_MODEL = os.environ.get("FACTORY_LLM_MODEL", "claude-opus-5")

_SYSTEM_PROMPT = """\
Tu sélectionnes des moments de podcast pour des clips TikTok/Reels/Shorts.
Un bon moment : accroche dans les 2 premières secondes, charge émotionnelle
ou informationnelle forte, et surtout AUTONOME — compréhensible sans avoir
écouté le reste. Fenêtres de 20 à 60 secondes, alignées sur les horodatages
fournis. Note hook, emotion et autonomy sur 10, sévèrement : la moyenne d'un
podcast ordinaire est autour de 4-5, réserve 8+ aux moments réellement
clipables. La justification (1-2 phrases) explique pourquoi ce moment peut
performer, dans la langue du transcript."""


class ClaudeScorer:
    def __init__(self, model: str = DEFAULT_LLM_MODEL, client=None):
        import anthropic

        self.model = model
        self.name = model
        self.client = client or anthropic.Anthropic()

    def find_moments(
        self, segments: list[Segment], language: str, top_n: int = 5
    ) -> list[MomentCandidate]:
        from pydantic import BaseModel

        class Candidate(BaseModel):
            start_s: float
            end_s: float
            title: str
            hook: float
            emotion: float
            autonomy: float
            justification: str

        class Selection(BaseModel):
            moments: list[Candidate]

        transcript = "\n".join(
            f"[{s.start:.1f}–{s.end:.1f}] {s.text}" for s in segments
        )
        response = self.client.messages.parse(
            model=self.model,
            max_tokens=16000,
            system=_SYSTEM_PROMPT,
            messages=[{
                "role": "user",
                "content": (
                    f"Langue du transcript : {language}. Sélectionne les "
                    f"{top_n} meilleurs moments.\n\n{transcript}"
                ),
            }],
            output_format=Selection,
        )
        clamp = lambda v: max(0.0, min(10.0, float(v)))
        end_of_audio = segments[-1].end if segments else 0.0
        out: list[MomentCandidate] = []
        for m in response.parsed_output.moments:
            start = max(0.0, min(m.start_s, end_of_audio))
            end = max(0.0, min(m.end_s, end_of_audio))
            if end - start < MIN_LEN_S / 2 or end - start > HARD_MAX_LEN_S:
                continue
            out.append(
                MomentCandidate(
                    t_start=start, t_end=end, title=m.title[:120],
                    hook=clamp(m.hook), emotion=clamp(m.emotion),
                    autonomy=clamp(m.autonomy),
                    justification=m.justification,
                )
            )
        return out[:top_n]


# ---------------------------------------------------------------------------
# Gate G2 + persistance
# ---------------------------------------------------------------------------

def g2_min_score() -> float:
    try:
        return float(os.environ.get("G2_MIN_SCORE", "7.0"))
    except ValueError:
        return 7.0


def save_moments(
    conn: sqlite3.Connection,
    episode_id: int,
    candidates: list[MomentCandidate],
    scorer_name: str,
) -> int:
    """Persiste les moments, applique G2, passe l'épisode en 'scored'.

    Renvoie le nombre de moments qui passent G2.
    """
    threshold = g2_min_score()
    passed = 0
    conn.execute("DELETE FROM moments WHERE episode_id=?", (episode_id,))
    for c in candidates:
        ok = c.score >= threshold
        passed += int(ok)
        conn.execute(
            "INSERT INTO moments (episode_id, t_start, t_end, title, score_hook,"
            " score_emotion, score_autonomy, score, justification, scorer,"
            " g2_passed, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                episode_id, c.t_start, c.t_end, c.title, c.hook, c.emotion,
                c.autonomy, c.score, c.justification, scorer_name,
                int(ok), utcnow().isoformat(),
            ),
        )
    conn.execute(
        "UPDATE episodes SET status='scored' WHERE id=?", (episode_id,)
    )
    conn.commit()
    return passed
