import json
import subprocess
from pathlib import Path

import pytest

from factory import db, ingest
from factory.compliance import AI_BADGE, COMMERCIAL_BADGE, RenderMeta, check, default_badges
from factory.moments import MomentCandidate, save_moments
from factory.produce import produce_moment
from factory.reaction import Interruption, ReactionScript, TemplateReactionWriter, FixtureReactionWriter
from factory.render import _ass_time, build_timeline, concat_audio, probe_duration, write_ass
from factory.transcribe import FixtureTranscriber, Segment, transcribe_episode
from factory.tts import FixtureTTS

SEGMENTS = [
    Segment(5.0, 12.0, "Tu sais pourquoi 90% des créateurs échouent ?"),
    Segment(12.0, 20.0, "Personne ne leur explique le modèle économique !"),
    Segment(20.0, 30.0, "Moi j'ai perdu 50 000 euros la première année."),
]


def make_source_audio(path: Path, duration: float = 40.0) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi",
         "-i", f"sine=frequency=220:duration={duration}",
         "-ar", "44100", "-ac", "2", str(path)],
        check=True,
    )
    return path


# ---------------------------------------------------------------------------
# Compliance (G3)
# ---------------------------------------------------------------------------

def _meta(**overrides) -> RenderMeta:
    base = dict(
        duration_s=45.0,
        credit_text="Extrait — Podcast X",
        badges=default_badges(is_campaign=True),
        is_campaign=True,
        music_cleared=True,
        authorization_kind="campaign",
    )
    base.update(overrides)
    return RenderMeta(**base)


def test_g3_passes_compliant_render():
    assert check(_meta()) == []


def test_g3_blocks_each_violation():
    assert any("durée" in i for i in check(_meta(duration_s=5.0)))
    assert any("crédit" in i for i in check(_meta(credit_text="  ")))
    assert any("Collaboration commerciale" in i
               for i in check(_meta(badges=[AI_BADGE])))
    assert any("IA" in i for i in check(_meta(badges=[COMMERCIAL_BADGE])))
    assert any("musique" in i for i in check(_meta(music_cleared=False)))


def test_default_badges():
    assert default_badges(True) == [COMMERCIAL_BADGE, AI_BADGE]
    assert default_badges(False) == [AI_BADGE]


# ---------------------------------------------------------------------------
# Timeline & ASS
# ---------------------------------------------------------------------------

def test_ass_time_format():
    assert _ass_time(0) == "0:00:00.00"
    assert _ass_time(3661.5) == "1:01:01.50"


def test_build_timeline_structure(tmp_path):
    source = make_source_audio(tmp_path / "src.wav")
    script = ReactionScript(
        hook="Écoute bien.",
        interruptions=[Interruption(at_s=10.0, text="Stop, on en parle.")],
        outro="T'en penses quoi ?",
    )
    items = build_timeline(
        source, 5.0, 30.0, SEGMENTS, script, FixtureTTS(), "fr", tmp_path / "work"
    )
    kinds = [i.kind for i in items]
    assert kinds == ["reaction", "clip", "reaction", "clip", "reaction"]
    # la coupure tombe à 10 s relatives → parties de 10 s et 15 s
    assert items[1].duration == pytest.approx(10.0, abs=0.3)
    assert items[3].duration == pytest.approx(15.0, abs=0.3)
    # captions du clip rebasées sur le début de la partie
    first_clip_caps = items[1].captions
    assert first_clip_caps[0][0] == pytest.approx(0.0, abs=0.01)
    assert "90%" in first_clip_caps[0][2]


def test_interruption_out_of_bounds_ignored(tmp_path):
    source = make_source_audio(tmp_path / "src.wav")
    script = ReactionScript(
        hook="Hook.",
        interruptions=[Interruption(at_s=200.0, text="jamais joué")],
        outro="",
    )
    items = build_timeline(
        source, 5.0, 30.0, SEGMENTS, script, FixtureTTS(), "fr", tmp_path / "work"
    )
    assert [i.kind for i in items] == ["reaction", "clip"]


def test_write_ass_styles_and_events(tmp_path):
    source = make_source_audio(tmp_path / "src.wav")
    items = build_timeline(
        source, 5.0, 30.0, SEGMENTS,
        ReactionScript(hook="Hook !", outro="Fin."),
        FixtureTTS(), "fr", tmp_path / "work",
    )
    _, offsets = concat_audio(items, tmp_path / "work")
    total = sum(i.duration for i in items)
    ass = write_ass(
        items, offsets, total, tmp_path / "subs.ass",
        "Extrait — Podcast X", [AI_BADGE],
    )
    content = ass.read_text(encoding="utf-8")
    assert "Style: Clip" in content and "Style: Reaction" in content
    assert ",Reaction,,0,0,0,,Hook !" in content
    assert ",Credit,,0,0,0,,Extrait — Podcast X" in content
    assert AI_BADGE in content


# ---------------------------------------------------------------------------
# Production de bout en bout (rendu ffmpeg réel)
# ---------------------------------------------------------------------------

def _prepared_pipeline(tmp_path, authorization="campaign"):
    conn = db.connect(str(tmp_path / "test.db"))
    ingest.add_source(
        conn, kind="podcast_rss", name="Podcast X", language="fr",
        authorization_kind=authorization, authorization_proof="campagne whop:x",
        feed_url="https://example.com/feed.xml",
    )
    feed = (Path(__file__).parent / "fixtures" / "podcast_feed.xml").read_text()
    ingest.scan_sources(conn, fetch=lambda url: feed)
    audio = make_source_audio(tmp_path / "media" / "episode-1.wav")
    conn.execute(
        "UPDATE episodes SET status='fetched', audio_path=? WHERE id=1",
        (str(audio),),
    )
    transcribe_episode(conn, 1, FixtureTranscriber(SEGMENTS), tmp_path / "media")
    moments = [MomentCandidate(
        t_start=5.0, t_end=30.0, title="Le modèle économique",
        hook=9, emotion=8, autonomy=8, justification="test",
    )]
    save_moments(conn, 1, moments, "test")
    return conn


def test_produce_moment_end_to_end(tmp_path):
    conn = _prepared_pipeline(tmp_path)
    script = ReactionScript(
        hook="Écoute bien ça.",
        interruptions=[Interruption(at_s=12.0, text="Stop. Là c'est important.")],
        outro="Dis-le en commentaire.",
    )
    result = produce_moment(
        conn, 1, FixtureReactionWriter(script), FixtureTTS(),
        tmp_path / "media", persona_png=None, music_cleared=True,
        width=270, height=480,
    )
    assert result.ok, result.issues
    assert result.out_path.exists()
    # durée = extrait 25 s + 3 prises de parole TTS
    assert 26.0 < result.duration_s < 60.0
    assert probe_duration(result.out_path) == pytest.approx(result.duration_s, abs=0.5)
    row = conn.execute("SELECT * FROM renders WHERE id=1").fetchone()
    assert row["ok"] == 1 and json.loads(row["issues"]) == []


def test_produce_blocks_without_music_attestation(tmp_path):
    conn = _prepared_pipeline(tmp_path)
    result = produce_moment(
        conn, 1, TemplateReactionWriter(), FixtureTTS(),
        tmp_path / "media", music_cleared=False, width=270, height=480,
    )
    assert not result.ok
    assert any("musique" in i for i in result.issues)
    assert conn.execute("SELECT ok FROM renders WHERE id=1").fetchone()[0] == 0


def test_produce_refuses_g2_failed_moment(tmp_path):
    conn = _prepared_pipeline(tmp_path)
    conn.execute("UPDATE moments SET g2_passed=0 WHERE id=1")
    with pytest.raises(ValueError, match="G2"):
        produce_moment(
            conn, 1, TemplateReactionWriter(), FixtureTTS(), tmp_path / "media",
        )
