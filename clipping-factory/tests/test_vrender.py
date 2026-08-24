import subprocess

import pytest

from factory.reaction import Interruption, ReactionScript
from factory.render import probe_duration
from factory.transcribe import Segment
from factory.tts import FixtureTTS
from factory.vrender import (
    has_video_stream,
    plan_voice_cues,
    produce_dynamic_video,
    punch_boundaries,
)

SEGMENTS = [
    Segment(5.0, 12.0, "Tu sais pourquoi 90% échouent ?"),
    Segment(12.0, 20.0, "Personne ne leur explique le modèle !"),
    Segment(20.0, 30.0, "Moi j'ai perdu 50 000 euros."),
]

SCRIPT = ReactionScript(
    hook="Écoute ça.",
    interruptions=[Interruption(at_s=12.0, text="Stop, c'est important.")],
    outro="Ton avis ?",
)


def make_source_video(path, duration=40.0):
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error",
         "-f", "lavfi", "-i", f"testsrc2=size=640x360:rate=30:duration={duration}",
         "-f", "lavfi", "-i", f"sine=frequency=220:duration={duration}",
         "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
         "-c:a", "aac", str(path)],
        check=True,
    )
    return path


def make_green_persona(path):
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (300, 300), (0, 255, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([60, 60, 240, 240], fill=(79, 200, 255))
    img.save(path)
    return path


def test_has_video_stream(tmp_path):
    video = make_source_video(tmp_path / "src.mp4", 3.0)
    assert has_video_stream(video)
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
         "-i", "sine=frequency=220:duration=2", str(tmp_path / "a.wav")],
        check=True,
    )
    assert not has_video_stream(tmp_path / "a.wav")


def test_punch_boundaries_spacing():
    bounds = punch_boundaries(SEGMENTS, 5.0, 30.0)
    assert bounds[0] == 5.0 and bounds[-1] == 30.0
    assert bounds == sorted(bounds)
    for a, b in zip(bounds, bounds[1:]):
        assert b - a >= 1.2


def test_plan_voice_cues_no_overlap(tmp_path):
    cues = plan_voice_cues(SCRIPT, FixtureTTS(), "fr", tmp_path, 25.0, 5.0)
    assert len(cues) == 3
    for prev, nxt in zip(cues, cues[1:]):
        assert nxt.start >= prev.start + prev.duration
    # l'outro démarre après la fin de l'extrait
    assert cues[-1].start >= 25.0


def test_dynamic_end_to_end(tmp_path):
    video = make_source_video(tmp_path / "src.mp4", 40.0)
    persona = make_green_persona(tmp_path / "persona.png")
    out = produce_dynamic_video(
        video, 5.0, 30.0, SEGMENTS, SCRIPT, FixtureTTS(), "fr",
        tmp_path / "work", tmp_path / "master.mp4",
        "Extrait — Source Test", ["Persona IA"], persona,
        width=270, height=480,
    )
    dur = probe_duration(out)
    # extrait 25 s + queue outro ; le hook et l'interruption sont en overlay
    assert 25.0 < dur < 40.0
    assert has_video_stream(out)
