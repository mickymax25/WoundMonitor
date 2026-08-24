"""Station S6, mode vidéo — montage DYNAMIQUE pour podcasts filmés.

Style « monteur pro TikTok » (v3, d'après les retours du bêta test) :
- la vidéo ne s'arrête JAMAIS : le persona commente par-dessus, l'audio de
  l'extrait est abaissé (duck) pendant ses prises de parole ;
- punch-ins alternés : à chaque phrase, léger changement de zoom (l'effet
  jump-cut qui donne le rythme) ;
- persona ANIMÉ en continu : boucle alpha pré-rendue (flottement,
  balancement, pulsation) incrustée en bas à droite pendant les
  interventions ;
- sous-titres karaoké de l'extrait en bas, texte du persona en haut,
  barre de progression.

Tout reste ffmpeg + Pillow : déterministe, CPU-only, zéro licence.
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path

from .reaction import ReactionScript
from .render import TimelineItem, VIDEO_H, VIDEO_W, probe_duration, run_ffmpeg, write_ass
from .transcribe import Segment

FPS = 30
_ENC = ["-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
        "-r", str(FPS), "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-ac", "2"]
DUCK_LEVEL = 0.16          # niveau de l'audio du clip sous la voix du persona
PUNCH_ZOOM = 1.065         # zoom des punch-ins alternés
MIN_CUT_SPACING = 1.2      # s — pas de jump cut plus rapproché


def has_video_stream(path: Path) -> bool:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v", "-show_entries",
         "stream=codec_type", "-of", "csv=p=0", str(path)],
        capture_output=True, text=True,
    )
    return "video" in out.stdout


# ---------------------------------------------------------------------------
# Persona animé (boucle alpha pré-rendue, réutilisée pour toutes les vidéos)
# ---------------------------------------------------------------------------

def key_persona(src_png: Path, out_png: Path) -> Path:
    """Détoure le fond vert (#00FF00) → PNG RGBA."""
    out_png.parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg([
        "-i", str(src_png),
        "-vf", "chromakey=0x00FF00:0.20:0.06,despill=type=green",
        "-frames:v", "1", "-c:v", "png", str(out_png),
    ])
    return out_png


def make_persona_loop(
    keyed_png: Path, out_webm: Path, target_w: int, seconds: float = 2.4,
) -> Path:
    """Boucle d'animation alpha : flottement + balancement + pulsation."""
    import math

    from PIL import Image

    src = Image.open(keyed_png).convert("RGBA")
    bbox = src.getbbox()  # recadre sur le personnage détouré
    if bbox:
        src = src.crop(bbox)
    scale = target_w / src.width
    base = src.resize((target_w, int(src.height * scale)), Image.LANCZOS)
    pad = int(base.height * 0.12)
    cw, ch = base.width + 2 * pad, base.height + 2 * pad

    frames_dir = out_webm.parent / (out_webm.stem + "-frames")
    frames_dir.mkdir(parents=True, exist_ok=True)
    n = int(seconds * FPS)
    for i in range(n):
        t = i / FPS
        bob = math.sin(2 * math.pi * t / seconds) * pad * 0.35
        rot = math.sin(2 * math.pi * t / seconds + 1.1) * 3.0
        pulse = 1.0 + 0.022 * math.sin(2 * math.pi * 2 * t / seconds)
        frame = Image.new("RGBA", (cw, ch), (0, 0, 0, 0))
        img = base.resize(
            (int(base.width * pulse), int(base.height * pulse)), Image.LANCZOS
        ).rotate(rot, expand=True, resample=Image.BICUBIC)
        frame.alpha_composite(
            img, ((cw - img.width) // 2, int((ch - img.height) // 2 + bob))
        )
        frame.save(frames_dir / f"f{i:03d}.png")

    run_ffmpeg([
        "-framerate", str(FPS), "-i", str(frames_dir / "f%03d.png"),
        "-c:v", "libvpx-vp9", "-pix_fmt", "yuva420p", "-b:v", "0", "-crf", "32",
        str(out_webm),
    ])
    return out_webm


# ---------------------------------------------------------------------------
# Corps vidéo : extrait continu avec punch-ins alternés
# ---------------------------------------------------------------------------

def _vertical_layout(width: int, height: int, zoom: float = 1.0) -> str:
    vf = (
        f"split[bg][fg];"
        f"[bg]scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},gblur=sigma=24,eq=brightness=-0.08[bgb];"
        f"[fg]scale={width}:-2[fgs];"
        f"[bgb][fgs]overlay=(W-w)/2:(H-h)/2"
    )
    if zoom > 1.0:
        vf += f",scale={int(width * zoom) // 2 * 2}:-2,crop={width}:{height}"
    return vf


def punch_boundaries(
    clip_segments: list[Segment], t_start: float, t_end: float
) -> list[float]:
    """Points de jump cut : les débuts de phrase, espacés d'au moins 1,2 s."""
    bounds = [t_start]
    for s in clip_segments:
        t = max(t_start, min(s.start, t_end))
        if t - bounds[-1] >= MIN_CUT_SPACING and t_end - t >= MIN_CUT_SPACING:
            bounds.append(t)
    bounds.append(t_end)
    return bounds


def build_clip_body(
    src: Path, clip_segments: list[Segment], t_start: float, t_end: float,
    workdir: Path, width: int, height: int,
) -> Path:
    """Extrait continu, re-monté en sous-segments au zoom alterné."""
    workdir.mkdir(parents=True, exist_ok=True)
    bounds = punch_boundaries(clip_segments, t_start, t_end)
    parts = []
    for i in range(len(bounds) - 1):
        zoom = PUNCH_ZOOM if i % 2 else 1.0
        part = workdir / f"body-{i:02d}.mp4"
        run_ffmpeg([
            "-ss", f"{bounds[i]:.3f}", "-to", f"{bounds[i + 1]:.3f}",
            "-i", str(src),
            "-filter_complex", _vertical_layout(width, height, zoom),
            *_ENC, str(part),
        ])
        parts.append(part)
    listing = workdir / "body.txt"
    listing.write_text("".join(f"file '{p.name}'\n" for p in parts), "utf-8")
    body = workdir / "body.mp4"
    run_ffmpeg(["-f", "concat", "-safe", "0", "-i", str(listing),
                "-c", "copy", str(body)])
    return body


# ---------------------------------------------------------------------------
# Assemblage final
# ---------------------------------------------------------------------------

@dataclass
class VoiceCue:
    start: float          # dans la timeline finale
    duration: float
    wav: Path
    text: str


def plan_voice_cues(
    script: ReactionScript, tts, language: str, workdir: Path,
    clip_duration: float, t_start: float,
) -> list[VoiceCue]:
    """Synthétise les voix et les place : hook au début, interruptions à leur
    horodatage, outro sur la fin gelée — sans chevauchement entre cues."""
    cues: list[VoiceCue] = []

    def add(text: str, tag: str, at: float) -> None:
        if not text:
            return
        wav = tts.synth(text, language, workdir / f"tts-{tag}.wav")
        dur = probe_duration(wav)
        if cues:
            prev = cues[-1]
            at = max(at, prev.start + prev.duration + 0.35)
        cues.append(VoiceCue(start=at, duration=dur, wav=wav, text=text))

    add(script.hook, "hook", 0.25)
    for k, itr in enumerate(script.interruptions):
        at = min(max(itr.at_s, 1.0), clip_duration - 1.0)
        add(itr.text, f"int{k}", at)
    add(script.outro, "outro", clip_duration + 0.2)
    return cues


def make_mixed_master(
    body: Path, cues: list[VoiceCue], workdir: Path,
) -> tuple[Path, float]:
    """Corps + mix audio complet (duck + voix), queue gelée pour l'outro.

    Sortie SANS habillage graphique : c'est l'entrée commune des deux
    finitions (ffmpeg ou HyperFrames). Renvoie (mixed.mp4, durée totale).
    """
    clip_dur = probe_duration(body)
    tail = max(0.0, (cues[-1].start + cues[-1].duration + 0.4) - clip_dur) if cues else 0.0
    total = clip_dur + tail
    windows = [(c.start, c.start + c.duration) for c in cues]
    enable = "+".join(f"between(t,{a:.2f},{b:.2f})" for a, b in windows) or "0"

    inputs = ["-i", str(body.resolve())]
    for cue in cues:
        inputs += ["-i", str(cue.wav.resolve())]
    filters = [
        f"[0:v]tpad=stop_mode=clone:stop_duration={tail:.3f}[vout]",
        f"[0:a]apad=pad_dur={tail:.3f},"
        f"volume=enable='{enable}':volume={DUCK_LEVEL}[a0]",
    ]
    amix_in = "[a0]"
    for j, cue in enumerate(cues):
        delay_ms = int(cue.start * 1000)
        filters.append(f"[{j + 1}:a]adelay={delay_ms}|{delay_ms}[v{j}]")
        amix_in += f"[v{j}]"
    if cues:
        filters.append(
            f"{amix_in}amix=inputs={len(cues) + 1}:normalize=0:duration=longest[aout]"
        )
    else:
        filters.append("[0:a]anull[aout]")

    mixed = workdir / "mixed.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", *inputs,
         "-filter_complex", ";".join(filters),
         "-map", "[vout]", "-map", "[aout]",
         "-t", f"{total:.3f}", *_ENC, str(mixed)],
        check=True,
    )
    return mixed, total


def render_dynamic(
    body: Path,
    cues: list[VoiceCue],
    clip_captions: list[tuple[float, float, str]],
    persona_loop: Path | None,
    workdir: Path,
    out_path: Path,
    credit_text: str,
    badges: list[str],
    width: int = VIDEO_W,
    height: int = VIDEO_H,
) -> Path:
    """Finition ffmpeg : sous-titres ASS + persona en boucle + barre."""
    mixed, total = make_mixed_master(body, cues, workdir)
    clip_dur = probe_duration(body)

    items = [TimelineItem("clip", body, clip_dur, clip_captions)]
    offsets = [0.0]
    for cue in cues:
        items.append(TimelineItem("reaction", cue.wav, cue.duration,
                                  [(0.0, cue.duration, cue.text)]))
        offsets.append(cue.start)
    ass_path = write_ass(items, offsets, total, workdir / "subs.ass",
                         credit_text, badges, width, height)

    windows = [(c.start, c.start + c.duration) for c in cues]
    enable = "+".join(f"between(t,{a:.2f},{b:.2f})" for a, b in windows) or "0"

    inputs = ["-i", mixed.name]
    filters = []
    vlast = "[0:v]"
    if persona_loop is not None and cues:
        inputs = ["-c:v", "libvpx-vp9", "-stream_loop", "-1",
                  "-i", str(persona_loop.resolve()), "-i", mixed.name]
        filters.append(
            f"[1:v][0:v]overlay=x=W-w-16:y=H-h-{int(height * 0.145)}"
            f":enable='{enable}':eof_action=repeat[pv]"
        )
        vlast = "[pv]"
        amap = "1:a"
    else:
        amap = "0:a"

    bar_h = max(6, int(height * 0.006))
    filters.append(
        f"{vlast}ass={ass_path.name}[sv];"
        f"[sv]drawbox=x=0:y=0:w='iw*t/{total:.3f}':h={bar_h}"
        f":color=0x4FC8FF@0.9:t=fill[vout]"
    )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", *inputs,
         "-filter_complex", ";".join(filters),
         "-map", "[vout]", "-map", amap,
         "-t", f"{total:.3f}", *_ENC, str(out_path.resolve())],
        check=True, cwd=workdir,
    )
    return out_path


def prepare_dynamic(
    source_video: Path,
    t_start: float,
    t_end: float,
    clip_segments: list[Segment],
    script: ReactionScript,
    tts,
    language: str,
    workdir: Path,
    width: int = VIDEO_W,
    height: int = VIDEO_H,
) -> tuple[Path, list[VoiceCue], list[tuple[float, float, str]]]:
    """Étage commun aux deux finitions : corps, voix planifiées, captions."""
    workdir.mkdir(parents=True, exist_ok=True)
    body = build_clip_body(
        source_video, clip_segments, t_start, t_end, workdir, width, height
    )
    clip_dur = probe_duration(body)
    cues = plan_voice_cues(script, tts, language, workdir, clip_dur, t_start)
    captions = []
    for s in clip_segments:
        lo, hi = max(s.start, t_start), min(s.end, t_end)
        if hi - lo > 0.2:
            captions.append((lo - t_start, hi - t_start, s.text))
    return body, cues, captions


def produce_dynamic_video(
    source_video: Path,
    t_start: float,
    t_end: float,
    clip_segments: list[Segment],
    script: ReactionScript,
    tts,
    language: str,
    workdir: Path,
    out_path: Path,
    credit_text: str,
    badges: list[str],
    persona_png: Path | None,
    width: int = VIDEO_W,
    height: int = VIDEO_H,
) -> Path:
    """Orchestration complète du montage dynamique (finition ffmpeg)."""
    body, cues, captions = prepare_dynamic(
        source_video, t_start, t_end, clip_segments, script, tts, language,
        workdir, width, height,
    )
    loop = None
    if persona_png is not None:
        keyed = key_persona(persona_png, workdir / "persona-keyed.png")
        loop = make_persona_loop(
            keyed, workdir / "persona-loop.webm", int(width * 0.34)
        )
    return render_dynamic(
        body, cues, captions, loop, workdir, out_path,
        credit_text, badges, width, height,
    )
