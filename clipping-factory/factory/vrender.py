"""Station S6, mode vidéo — rendu production pour podcasts FILMÉS.

Différences avec le mode audio (`render.py`) :
- les parties « extrait » montrent la vraie vidéo, recadrée en vertical
  (premier plan ajusté à la largeur, arrière-plan = même image agrandie,
  floutée et assombrie) ;
- les prises de parole du persona sont des cartes plein écran : fond
  dégradé + personnage centré dont la bouche s'anime pendant qu'il parle ;
- passe finale commune : sous-titres ASS karaoké + barre de progression.

Chaque segment est encodé aux mêmes paramètres (H.264/AAC, même fps) puis
concaténé sans ré-encodage ; idempotent et rejouable comme les autres
stations.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from .reaction import ReactionScript
from .render import (
    TimelineItem, VIDEO_H, VIDEO_W, probe_duration, run_ffmpeg, write_ass,
)
from .transcribe import Segment

FPS = 30
_ENC = ["-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
        "-r", str(FPS), "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-ac", "2"]


def has_video_stream(path: Path) -> bool:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries",
         "stream=codec_type", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True,
    )
    return "video" in out.stdout


def clip_video_segment(
    src: Path, start: float, end: float, out: Path,
    width: int = VIDEO_W, height: int = VIDEO_H,
) -> Path:
    """Extrait vidéo recadré vertical : fond flouté plein cadre + premier plan."""
    out.parent.mkdir(parents=True, exist_ok=True)
    vf = (
        f"split[bg][fg];"
        f"[bg]scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},gblur=sigma=24,eq=brightness=-0.08[bgb];"
        f"[fg]scale={width}:-2[fgs];"
        f"[bgb][fgs]overlay=(W-w)/2:(H-h)/2"
    )
    run_ffmpeg([
        "-ss", f"{start:.3f}", "-to", f"{end:.3f}", "-i", str(src),
        "-filter_complex", vf, *_ENC, str(out),
    ])
    return out


def reaction_freeze_segment(
    src: Path, freeze_t: float, voice_wav: Path, persona_png: Path | None,
    out: Path, width: int = VIDEO_W, height: int = VIDEO_H,
) -> Path:
    """Intervention du persona : la vidéo se FIGE (image du point de coupe,
    légèrement assombrie), le persona apparaît détouré en bas à droite avec
    un flottement subtil — aucune animation de bouche."""
    out.parent.mkdir(parents=True, exist_ok=True)
    duration = probe_duration(voice_wav)

    # image gelée, au même cadrage que les segments d'extrait
    freeze = out.with_suffix(".freeze.png")
    vf = (
        f"split[bg][fg];"
        f"[bg]scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},gblur=sigma=24,eq=brightness=-0.08[bgb];"
        f"[fg]scale={width}:-2[fgs];"
        f"[bgb][fgs]overlay=(W-w)/2:(H-h)/2,eq=brightness=-0.12:saturation=0.85"
    )
    run_ffmpeg([
        "-ss", f"{max(0.0, freeze_t):.3f}", "-i", str(src),
        "-frames:v", "1", "-filter_complex", vf, str(freeze),
    ])

    inputs = ["-loop", "1", "-i", str(freeze), "-i", str(voice_wav)]
    if persona_png is not None:
        pw = int(width * 0.38)
        margin_y = int(height * 0.155)
        inputs += ["-loop", "1", "-i", str(persona_png)]
        filters = (
            f"[2]chromakey=0x00FF00:0.20:0.06,despill=type=green,"
            f"scale={pw}:-1[p];"
            f"[0][p]overlay=x=W-w-20:y=H-h-{margin_y}+9*sin(2*PI*t/2.6)"
        )
        run_ffmpeg([*inputs, "-filter_complex", filters,
                    "-t", f"{duration:.3f}", *_ENC, "-shortest", str(out)])
    else:
        run_ffmpeg([*inputs, "-t", f"{duration:.3f}", *_ENC,
                    "-shortest", str(out)])
    return out


def build_video_timeline(
    source_video: Path,
    t_start: float,
    t_end: float,
    clip_segments: list[Segment],
    script: ReactionScript,
    tts,
    language: str,
    workdir: Path,
    persona_png: Path | None,
    width: int = VIDEO_W,
    height: int = VIDEO_H,
) -> list[TimelineItem]:
    """Même structure hook → extrait coupé → outro, en segments VIDÉO.

    Renvoie des TimelineItem dont `audio_path` pointe vers le segment mp4
    (le champ porte le média du segment ; les captions restent identiques).
    """
    workdir.mkdir(parents=True, exist_ok=True)

    def reaction_item(text: str, tag: str, freeze_t: float) -> TimelineItem:
        wav = tts.synth(text, language, workdir / f"tts-{tag}.wav")
        seg = reaction_freeze_segment(
            source_video, freeze_t, wav, persona_png,
            workdir / f"vseg-{tag}.mp4", width, height,
        )
        dur = probe_duration(seg)
        return TimelineItem("reaction", seg, dur, [(0.0, dur, text)])

    def clip_item(a: float, b: float, tag: str) -> TimelineItem:
        seg = clip_video_segment(
            source_video, a, b, workdir / f"vseg-clip-{tag}.mp4", width, height,
        )
        dur = probe_duration(seg)
        captions = []
        for s in clip_segments:
            lo, hi = max(s.start, a), min(s.end, b)
            if hi - lo > 0.2:
                captions.append((lo - a, hi - a, s.text))
        return TimelineItem("clip", seg, dur, captions)

    items: list[TimelineItem] = []
    if script.hook:
        items.append(reaction_item(script.hook, "hook", t_start + 0.2))
    cuts = [t_start + i.at_s for i in script.interruptions
            if 1.0 < i.at_s < (t_end - t_start) - 1.0]
    bounds = [t_start, *cuts, t_end]
    for idx in range(len(bounds) - 1):
        items.append(clip_item(bounds[idx], bounds[idx + 1], str(idx)))
        if idx < len(cuts):
            items.append(reaction_item(
                script.interruptions[idx].text, f"int{idx}", cuts[idx]
            ))
    if script.outro:
        items.append(reaction_item(script.outro, "outro", t_end - 0.2))
    return items


def render_video_master(
    items: list[TimelineItem],
    workdir: Path,
    out_path: Path,
    credit_text: str,
    badges: list[str],
    width: int = VIDEO_W,
    height: int = VIDEO_H,
) -> Path:
    """Concatène les segments et applique la passe finale (ASS + progression)."""
    listing = workdir / "vconcat.txt"
    listing.write_text(
        "".join(f"file '{item.audio_path.name}'\n" for item in items),
        encoding="utf-8",
    )
    joined = workdir / "joined.mp4"
    run_ffmpeg(["-f", "concat", "-safe", "0", "-i", str(listing),
                "-c", "copy", str(joined)])

    offsets, t = [], 0.0
    for item in items:
        offsets.append(t)
        t += item.duration
    total = t
    ass_path = write_ass(
        items, offsets, total, workdir / "subs.ass", credit_text, badges,
        width, height,
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    bar_h = max(6, int(height * 0.006))
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-i", joined.name,
         "-filter_complex",
         f"[0]ass={ass_path.name}[sub];"
         f"[sub]drawbox=x=0:y=0:w='iw*t/{total:.3f}':h={bar_h}"
         f":color=0x4FC8FF@0.9:t=fill[vout]",
         "-map", "[vout]", "-map", "0:a",
         "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
         "-c:a", "copy", str(out_path.resolve())],
        check=True, cwd=workdir,
    )
    return out_path
