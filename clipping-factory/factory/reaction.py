"""Station S4 — écriture de la réaction du persona.

La réaction est LE produit (RESEARCH.md §4, décision n°4) : elle doit
ANALYSER l'extrait — prendre position, contextualiser, contredire — pas le
décorer. C'est ce qui fait passer le filtre d'originalité TikTok et ce qui
fonde la défense « critique » côté droit. Structure produite :

    hook (avant l'extrait) → interruptions datées (le persona coupe
    l'extrait) → outro (chute + relance).

Comme en S3 : un writer LLM (sorties structurées) et un writer fixture
pour les tests/rejeu.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Protocol

from .transcribe import Segment

DEFAULT_LLM_MODEL = os.environ.get("FACTORY_LLM_MODEL", "claude-opus-5")

DEFAULT_PERSONA = os.environ.get(
    "FACTORY_PERSONA",
    "Nova, persona 100% fictif et assumé comme IA : commentateur vif, "
    "sceptique et drôle, qui vulgarise et n'hésite pas à contredire. "
    "Ton oral, phrases courtes, pas de vulgarité, jamais d'imitation "
    "d'une personne réelle.",
)


@dataclass
class Interruption:
    at_s: float          # position DANS l'extrait (relative, secondes)
    text: str


@dataclass
class ReactionScript:
    hook: str            # avant l'extrait, < ~2 s à l'écran
    interruptions: list[Interruption] = field(default_factory=list)
    outro: str = ""

    def all_texts(self) -> list[str]:
        return [self.hook, *[i.text for i in self.interruptions], self.outro]


class ReactionWriter(Protocol):
    name: str

    def write(
        self, clip_segments: list[Segment], language: str, moment_title: str
    ) -> ReactionScript: ...


_SYSTEM_PROMPT = """\
Tu écris la réaction d'un persona pour un clip TikTok/Reels/Shorts.
Persona : {persona}

Contraintes non négociables :
- La réaction ANALYSE l'extrait : elle prend position, apporte un fait ou un
  contexte, souligne une contradiction — jamais du simple hype décoratif.
- hook : une phrase choc dite AVANT l'extrait, qui donne envie de rester,
  sans divulgâcher la chute. 12 mots max.
- 1 à 2 interruptions : le persona COUPE l'extrait à un horodatage précis
  (champ at_s, en secondes relatives au début de l'extrait, aligné sur les
  horodatages fournis) pour réagir en 1-2 phrases orales.
- outro : la chute du persona + une question qui provoque les commentaires.
- Langue de sortie : celle du transcript. Style oral, rythmé, phrases courtes.
"""


class ClaudeReactionWriter:
    def __init__(
        self,
        model: str = DEFAULT_LLM_MODEL,
        persona: str = DEFAULT_PERSONA,
        client=None,
    ):
        import anthropic

        self.model = model
        self.name = model
        self.persona = persona
        self.client = client or anthropic.Anthropic()

    def write(
        self, clip_segments: list[Segment], language: str, moment_title: str
    ) -> ReactionScript:
        from pydantic import BaseModel

        class InterruptionOut(BaseModel):
            at_s: float
            text: str

        class ScriptOut(BaseModel):
            hook: str
            interruptions: list[InterruptionOut]
            outro: str

        t0 = clip_segments[0].start if clip_segments else 0.0
        excerpt = "\n".join(
            f"[{s.start - t0:.1f}–{s.end - t0:.1f}] {s.text}" for s in clip_segments
        )
        response = self.client.messages.parse(
            model=self.model,
            max_tokens=16000,
            system=_SYSTEM_PROMPT.format(persona=self.persona),
            messages=[{
                "role": "user",
                "content": (
                    f"Langue : {language}. Titre du moment : {moment_title}\n\n"
                    f"Extrait horodaté (secondes relatives) :\n{excerpt}"
                ),
            }],
            output_format=ScriptOut,
        )
        out = response.parsed_output
        clip_len = (clip_segments[-1].end - t0) if clip_segments else 0.0
        interruptions = [
            Interruption(at_s=max(0.0, min(i.at_s, clip_len)), text=i.text.strip())
            for i in out.interruptions[:2]
            if i.text.strip()
        ]
        interruptions.sort(key=lambda i: i.at_s)
        return ReactionScript(
            hook=out.hook.strip(),
            interruptions=interruptions,
            outro=out.outro.strip(),
        )


class TemplateReactionWriter:
    """Réaction générique par gabarits FR/EN — démo et mode dégradé sans API.

    Qualité volontairement basique : le chemin de production est le writer
    LLM ; ce gabarit sert à faire tourner la chaîne de bout en bout.
    """

    name = "template"

    _TEMPLATES = {
        "fr": ReactionScript(
            hook="Attends… écoute bien ce qu'il dit là.",
            interruptions=[Interruption(
                at_s=0.0,
                text="Stop. Là il faut qu'on en parle, parce que c'est"
                     " exactement le point que tout le monde rate.",
            )],
            outro="Voilà pourquoi ce passage est important. Toi, t'en penses"
                  " quoi ? Dis-le en commentaire.",
        ),
        "en": ReactionScript(
            hook="Wait… listen to what he says right here.",
            interruptions=[Interruption(
                at_s=0.0,
                text="Stop. We need to talk about this, because this is"
                     " exactly the point everyone misses.",
            )],
            outro="That's why this moment matters. What do you think?"
                  " Tell me in the comments.",
        ),
    }

    def write(
        self, clip_segments: list[Segment], language: str, moment_title: str
    ) -> ReactionScript:
        lang = "fr" if language.startswith("fr") else "en"
        base = self._TEMPLATES[lang]
        clip_len = (
            clip_segments[-1].end - clip_segments[0].start if clip_segments else 0.0
        )
        return ReactionScript(
            hook=base.hook,
            interruptions=[
                Interruption(at_s=round(clip_len / 2, 1), text=i.text)
                for i in base.interruptions
            ],
            outro=base.outro,
        )


class FixtureReactionWriter:
    """Script fourni d'avance — tests et rejeu hors ligne."""

    name = "fixture"

    def __init__(self, script: ReactionScript):
        self.script = script

    def write(
        self, clip_segments: list[Segment], language: str, moment_title: str
    ) -> ReactionScript:
        return self.script
