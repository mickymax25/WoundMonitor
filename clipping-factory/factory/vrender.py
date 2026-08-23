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


def reaction_card_segment(
    voice_wav: Path, bg_png: Path, persona_closed: Path, persona_open: Path,
    out: Path, width: int = VIDEO_W, height: int = VIDEO_H,
) -> Path:
    """Carte persona plein écran : dégradé + personnage, bouche animée 4 Hz."""
    out.parent.mkdir(parents=True, exist_ok=True)
    duration = probe_duration(voice_wav)
    pw = int(width * 0.52)
    y = f"(H-h)/2-{int(height * 0.08)}"
    run_ffmpeg([
        "-loop", "1", "-i", str(bg_png),
        "-i", str(voice_wav),
        "-loop", "1", "-i", str(persona_closed),
        "-loop", "1", "-i", str(persona_open),
        "-filter_complex",
        (
            f"[2]scale={pw}:-1[pc];[3]scale={pw}:-1[po];"
            f"[0][pc]overlay=(W-w)/2:{y}:enable='gte(mod(t,0.25),0.125)'[s1];"
            f"[s1][po]overlay=(W-w)/2:{y}:enable='lt(mod(t,0.25),0.125)'"
        ),
        "-t", f"{duration:.3f}", *_ENC, "-shortest", str(out),
    ])
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
    bg_png: Path,
    persona_closed: Path,
    persona_open: Path,
    width: int = VIDEO_W,
    height: int = VIDEO_H,
) -> list[TimelineItem]:
    """Même structure hook → extrait coupé → outro, en segments VIDÉO.

    Renvoie des TimelineItem dont `audio_path` pointe vers le segment mp4
    (le champ porte le média du segment ; les captions restent identiques).
    """
    workdir.mkdir(parents=True, exist_ok=True)

    def reaction_item(text: str, tag: str) -> TimelineItem:
        wav = tts.synth(text, language, workdir / f"tts-{tag}.wav")
        seg = reaction_card_segment(
            wav, bg_png, persona_closed, persona_open,
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
        items.append(reaction_item(script.hook, "hook"))
    cuts = [t_start + i.at_s for i in script.interruptions
            if 1.0 < i.at_s < (t_end - t_start) - 1.0]
    bounds = [t_start, *cuts, t_end]
    for idx in range(len(bounds) - 1):
        items.append(clip_item(bounds[idx], bounds[idx + 1], str(idx)))
        if idx < len(cuts):
            items.append(reaction_item(script.interruptions[idx].text, f"int{idx}"))
    if script.outro:
        items.append(reaction_item(script.outro, "outro"))
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
