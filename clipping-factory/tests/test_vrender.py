import subprocess

import pytest

from factory.reaction import Interruption, ReactionScript
from factory.render import probe_duration
from factory.transcribe import Segment
from factory.tts import FixtureTTS
from factory.vrender import build_video_timeline, has_video_stream, render_video_master

SEGMENTS = [
    Segment(5.0, 12.0, "Tu sais pourquoi 90% échouent ?"),
    Segment(12.0, 20.0, "Personne ne leur explique le modèle !"),
    Segment(20.0, 30.0, "Moi j'ai perdu 50 000 euros."),
]


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


def test_has_video_stream(tmp_path):
    video = make_source_video(tmp_path / "src.mp4", 3.0)
    assert has_video_stream(video)
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
         "-i", "sine=frequency=220:duration=2", str(tmp_path / "a.wav")],
        check=True,
    )
    assert not has_video_stream(tmp_path / "a.wav")


def make_green_persona(path):
    from PIL import Image, ImageDraw

    img = Image.new("RGB", (300, 300), (0, 255, 0))
    d = ImageDraw.Draw(img)
    d.ellipse([60, 60, 240, 240], fill=(79, 200, 255))
    img.save(path)
    return path


def test_video_master_end_to_end(tmp_path):
    video = make_source_video(tmp_path / "src.mp4", 40.0)
    persona = make_green_persona(tmp_path / "persona.png")
    script = ReactionScript(
        hook="Écoute ça.",
        interruptions=[Interruption(at_s=12.0, text="Stop, c'est important.")],
        outro="Ton avis ?",
    )
    items = build_video_timeline(
        video, 5.0, 30.0, SEGMENTS, script, FixtureTTS(), "fr",
        tmp_path / "work", persona, width=270, height=480,
    )
    assert [i.kind for i in items] == ["reaction", "clip", "reaction", "clip",
                                      "reaction"]
    out = render_video_master(
        items, tmp_path / "work", tmp_path / "master.mp4",
        "Extrait — Source Test", ["Persona IA"], width=270, height=480,
    )
    total = sum(i.duration for i in items)
    assert probe_duration(out) == pytest.approx(total, abs=1.0)
    # le master contient bien de la vidéo et de l'audio
    assert has_video_stream(out)
