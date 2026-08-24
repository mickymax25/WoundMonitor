"""Orchestration S4→S7 : d'un moment validé G2 à une vidéo prête pour S8.

`produce_moment` fait tout le trajet : écriture de la réaction, synthèse
TTS, montage timeline, rendu vertical, contrôle G3, persistance du verdict.
Une vidéo bloquée par G3 est quand même rendue et enregistrée (ok=0) pour
que la file de validation montre POURQUOI elle est bloquée.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from . import compliance, render
from .models import utcnow
from .reaction import ReactionWriter
from .transcribe import Segment, load_transcript
from .tts import TTS


@dataclass
class ProduceResult:
    render_id: int
    out_path: Path
    duration_s: float
    issues: list[str]

    @property
    def ok(self) -> bool:
        return not self.issues


def produce_moment(
    conn: sqlite3.Connection,
    moment_id: int,
    writer: ReactionWriter,
    tts: TTS,
    media_dir: str | Path,
    persona_png: Path | None = None,
    music_cleared: bool = False,
    width: int = render.VIDEO_W,
    height: int = render.VIDEO_H,
) -> ProduceResult:
    row = conn.execute(
        """SELECT m.*, e.audio_path, e.transcript_path, e.title AS ep_title,
                  s.name AS source_name, s.language, s.authorization_kind,
                  s.campaign_key
           FROM moments m
           JOIN episodes e ON e.id = m.episode_id
           JOIN content_sources s ON s.id = e.source_id
           WHERE m.id = ?""",
        (moment_id,),
    ).fetchone()
    if row is None:
        raise ValueError(f"moment {moment_id} inconnu")
    if not row["g2_passed"]:
        raise ValueError(f"moment {moment_id} n'a pas passé G2 — pas de production")
    if not row["audio_path"] or not row["transcript_path"]:
        raise ValueError(f"moment {moment_id}: audio/transcript manquants")

    segments = load_transcript(Path(row["transcript_path"]))
    clip_segments: list[Segment] = [
        s for s in segments if s.end > row["t_start"] and s.start < row["t_end"]
    ]

    script = writer.write(clip_segments, row["language"], row["title"] or "")

    media_dir = Path(media_dir)
    workdir = media_dir / f"moment-{moment_id}"
    source_media = Path(row["audio_path"])

    is_campaign = row["authorization_kind"] == "campaign" or bool(row["campaign_key"])
    badges = compliance.default_badges(is_campaign)
    credit = f"Extrait — {row['source_name']} · {row['ep_title']}"[:110]
    out_path = media_dir / f"moment-{moment_id}.mp4"

    from . import vrender

    if vrender.has_video_stream(source_media):
        # mode vidéo dynamique : extrait continu à punch-ins alternés, voix du
        # persona par-dessus (clip ducké), persona animé incrusté bas-droite.
        # Finition HyperFrames (motion design GSAP) par défaut, ffmpeg en repli.
        import os

        renderer = os.environ.get("FACTORY_RENDERER", "hyperframes")
        if renderer == "hyperframes":
            from . import hfrender

            body, cues, captions = vrender.prepare_dynamic(
                source_media, row["t_start"], row["t_end"], clip_segments,
                script, tts, row["language"], workdir, width, height,
            )
            try:
                keyed = (vrender.key_persona(persona_png,
                                             workdir / "persona-keyed.png")
                         if persona_png else None)
                mixed, total = vrender.make_mixed_master(body, cues, workdir)
                hfrender.render_hyperframes(
                    mixed, total, captions, cues, keyed, workdir, out_path,
                    credit, badges, width, height,
                )
            except Exception as exc:
                print(f"⚠ finition HyperFrames indisponible ({exc}) — repli ffmpeg")
                loop = None
                if persona_png is not None:
                    keyed = vrender.key_persona(
                        persona_png, workdir / "persona-keyed.png")
                    loop = vrender.make_persona_loop(
                        keyed, workdir / "persona-loop.webm", int(width * 0.34))
                vrender.render_dynamic(
                    body, cues, captions, loop, workdir, out_path,
                    credit, badges, width, height,
                )
        else:
            vrender.produce_dynamic_video(
                source_media, row["t_start"], row["t_end"], clip_segments,
                script, tts, row["language"], workdir, out_path, credit, badges,
                persona_png, width=width, height=height,
            )
    else:
        items = render.build_timeline(
            source_media, row["t_start"], row["t_end"], clip_segments,
            script, tts, row["language"], workdir,
        )
        render.render_video(
            items, workdir, out_path, credit, badges, persona_png,
            width=width, height=height,
        )
    duration = render.probe_duration(out_path)

    issues = compliance.check(compliance.RenderMeta(
        duration_s=duration,
        credit_text=credit,
        badges=badges,
        is_campaign=is_campaign,
        music_cleared=music_cleared,
        authorization_kind=row["authorization_kind"],
    ))

    from .publish import file_checksum

    cur = conn.execute(
        "INSERT INTO renders (moment_id, path, duration_s, tts, writer, issues,"
        " ok, checksum, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
        (
            moment_id, str(out_path), duration, tts.name, writer.name,
            json.dumps(issues, ensure_ascii=False), int(not issues),
            file_checksum(out_path), utcnow().isoformat(),
        ),
    )
    conn.commit()
    return ProduceResult(
        render_id=cur.lastrowid, out_path=out_path,
        duration_s=duration, issues=issues,
    )
