"""Station S6 — fabrication de la vidéo verticale.

Entrées : l'audio source (autorisé), un moment (fenêtre S3), le script de
réaction (S4) et une voix TTS. Sortie : un MP4 vertical prêt pour la file
de validation, avec :

- la timeline hook → extrait (coupé par les interruptions) → outro ;
- sous-titres ASS burn-in, styles distincts extrait/réaction ;
- crédit source permanent + badges de conformité (mentions légales) rendus
  via l'ASS lui-même (pas de drawtext, escaping fragile) ;
- persona affiché à l'écran pendant les prises de parole de la réaction.

Tout passe par ffmpeg/libass : CPU-only, zéro licence (ARCHITECTURE.md §5).
"""

from __future__ import annotations

import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from .reaction import ReactionScript
from .transcribe import Segment

VIDEO_W, VIDEO_H = 1080, 1920
BG_COLOR = "0x14161B"
FPS = 30


@dataclass
class TimelineItem:
    kind: str                                   # 'reaction' | 'clip'
    audio_path: Path
    duration: float
    captions: list[tuple[float, float, str]] = field(default_factory=list)


def run_ffmpeg(args: list[str]) -> None:
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", *args], check=True
    )


def probe_duration(path: Path) -> float:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        check=True, capture_output=True, text=True,
    )
    return float(out.stdout.strip())


def extract_audio_span(source: Path, start: float, end: float, dst: Path) -> Path:
    dst.parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg([
        "-ss", f"{start:.3f}", "-to", f"{end:.3f}", "-i", str(source),
        "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le", str(dst),
    ])
    return dst


def to_wav(src: Path, dst: Path) -> Path:
    dst.parent.mkdir(parents=True, exist_ok=True)
    run_ffmpeg([
        "-i", str(src), "-ar", "44100", "-ac", "2", "-c:a", "pcm_s16le", str(dst)
    ])
    return dst


def build_timeline(
    source_audio: Path,
    t_start: float,
    t_end: float,
    clip_segments: list[Segment],
    script: ReactionScript,
    tts,
    language: str,
    workdir: Path,
) -> list[TimelineItem]:
    """Assemble hook → extrait (coupé aux interruptions) → outro."""
    workdir.mkdir(parents=True, exist_ok=True)
    items: list[TimelineItem] = []

    def reaction_item(text: str, tag: str) -> TimelineItem:
        raw = tts.synth(text, language, workdir / f"tts-{tag}.wav")
        wav = raw if raw.suffix == ".wav" else to_wav(raw, workdir / f"tts-{tag}-n.wav")
        dur = probe_duration(wav)
        return TimelineItem("reaction", wav, dur, [(0.0, dur, text)])

    def clip_item(a: float, b: float, tag: str) -> TimelineItem:
        wav = extract_audio_span(source_audio, a, b, workdir / f"clip-{tag}.wav")
        dur = probe_duration(wav)
        captions = []
        for s in clip_segments:
            lo, hi = max(s.start, a), min(s.end, b)
            if hi - lo > 0.2:
                captions.append((lo - a, hi - a, s.text))
        return TimelineItem("clip", wav, dur, captions)

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


def concat_audio(items: list[TimelineItem], workdir: Path) -> tuple[Path, list[float]]:
    """Concatène les audios ; renvoie (wav complet, offset de chaque item)."""
    listing = workdir / "concat.txt"
    listing.write_text(
        "".join(f"file '{item.audio_path.name}'\n" for item in items),
        encoding="utf-8",
    )
    full = workdir / "full.wav"
    run_ffmpeg([
        "-f", "concat", "-safe", "0", "-i", str(listing),
        "-c:a", "pcm_s16le", str(full),
    ])
    offsets, t = [], 0.0
    for item in items:
        offsets.append(t)
        t += item.duration
    return full, offsets


def _ass_time(seconds: float) -> str:
    cs = int(round(seconds * 100))
    h, rem = divmod(cs, 360000)
    m, rem = divmod(rem, 6000)
    s, cs = divmod(rem, 100)
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _ass_escape(text: str) -> str:
    return text.replace("\\", "").replace("{", "(").replace("}", ")").replace("\n", " ")


def write_ass(
    items: list[TimelineItem],
    offsets: list[float],
    total: float,
    path: Path,
    credit_text: str,
    badges: list[str],
    width: int = VIDEO_W,
    height: int = VIDEO_H,
) -> Path:
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
WrapStyle: 0

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Clip,DejaVu Sans,{int(height * 0.037)},&H00FFFFFF,&H00FFFFFF,&H00101010,&H80000000,-1,0,0,0,100,100,0,0,1,4,1,5,60,60,0,1
Style: Reaction,DejaVu Sans,{int(height * 0.040)},&H004FC8FF,&H00FFFFFF,&H00101010,&H80000000,-1,0,0,0,100,100,0,0,1,4,1,5,60,60,0,1
Style: Credit,DejaVu Sans,{int(height * 0.018)},&H00B4B4B4,&H00FFFFFF,&H00101010,&H80000000,0,0,0,0,100,100,0,0,1,2,0,2,40,40,40,1
Style: Badge,DejaVu Sans,{int(height * 0.018)},&H00B4B4B4,&H00FFFFFF,&H00101010,&H80000000,0,0,0,0,100,100,0,0,1,2,0,8,40,40,40,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [header]
    for item, offset in zip(items, offsets):
        style = "Reaction" if item.kind == "reaction" else "Clip"
        for start, end, text in item.captions:
            lines.append(
                f"Dialogue: 0,{_ass_time(offset + start)},{_ass_time(offset + end)},"
                f"{style},,0,0,0,,{_ass_escape(text)}\n"
            )
    if credit_text:
        lines.append(
            f"Dialogue: 0,{_ass_time(0)},{_ass_time(total)},Credit,,0,0,0,,"
            f"{_ass_escape(credit_text)}\n"
        )
    for badge in badges:
        lines.append(
            f"Dialogue: 0,{_ass_time(0)},{_ass_time(total)},Badge,,0,0,0,,"
            f"{_ass_escape(badge)}\n"
        )
    path.write_text("".join(lines), encoding="utf-8")
    return path


def reaction_ranges(
    items: list[TimelineItem], offsets: list[float]
) -> list[tuple[float, float]]:
    return [
        (off, off + item.duration)
        for item, off in zip(items, offsets)
        if item.kind == "reaction"
    ]


def render_video(
    items: list[TimelineItem],
    workdir: Path,
    out_path: Path,
    credit_text: str,
    badges: list[str],
    persona_png: Path | None = None,
    width: int = VIDEO_W,
    height: int = VIDEO_H,
    preset: str = "veryfast",
) -> Path:
    full, offsets = concat_audio(items, workdir)
    total = sum(i.duration for i in items)
    ass_path = write_ass(
        items, offsets, total, workdir / "subs.ass", credit_text, badges,
        width, height,
    )

    inputs = [
        "-f", "lavfi", "-i", f"color=c={BG_COLOR}:s={width}x{height}:r={FPS}",
        "-i", full.name,
    ]
    filters = []
    last = "[0]"
    if persona_png is not None:
        inputs += ["-loop", "1", "-i", str(persona_png)]
        enable = "+".join(
            f"between(t,{a:.2f},{b:.2f})" for a, b in reaction_ranges(items, offsets)
        ) or "0"
        pw = int(width * 0.33)
        filters.append(f"[2]scale={pw}:-1[persona]")
        filters.append(
            f"{last}[persona]overlay=x=W-w-30:y=H-h-{int(height * 0.16)}"
            f":enable='{enable}'[ov]"
        )
        last = "[ov]"
    filters.append(f"{last}ass={ass_path.name}[vout]")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", *inputs,
         "-filter_complex", ";".join(filters),
         "-map", "[vout]", "-map", "1:a",
         "-t", f"{total:.3f}",
         "-c:v", "libx264", "-preset", preset, "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "160k",
         str(out_path.resolve())],
        check=True, cwd=workdir,
    )
    return out_path
