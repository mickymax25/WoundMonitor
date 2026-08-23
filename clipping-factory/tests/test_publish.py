from pathlib import Path

import pytest

from factory import db, ingest, review, telemetry
from factory.moments import MomentCandidate, save_moments
from factory.produce import produce_moment
from factory.publish import DryRunPublisher, publish_render
from factory.reaction import TemplateReactionWriter
from factory.transcribe import FixtureTranscriber, Segment, transcribe_episode
from factory.tts import FixtureTTS

from test_produce import SEGMENTS, make_source_audio


@pytest.fixture
def ready(tmp_path):
    """Base avec un render conforme (G3 ✓) en file de validation."""
    conn = db.connect(str(tmp_path / "test.db"))
    ingest.add_source(
        conn, kind="podcast_rss", name="Podcast X", language="fr",
        authorization_kind="campaign", authorization_proof="campagne whop:x",
        feed_url="https://example.com/feed.xml",
    )
    feed = (Path(__file__).parent / "fixtures" / "podcast_feed.xml").read_text()
    ingest.scan_sources(conn, fetch=lambda url: feed)
    audio = make_source_audio(tmp_path / "media" / "episode-1.wav")
    conn.execute("UPDATE episodes SET status='fetched', audio_path=? WHERE id=1",
                 (str(audio),))
    transcribe_episode(conn, 1, FixtureTranscriber(SEGMENTS), tmp_path / "media")
    save_moments(conn, 1, [MomentCandidate(
        t_start=5.0, t_end=30.0, title="Titre", hook=9, emotion=8, autonomy=8,
        justification="test",
    )], "test")
    result = produce_moment(
        conn, 1, TemplateReactionWriter(), FixtureTTS(), tmp_path / "media",
        music_cleared=True, width=270, height=480,
    )
    assert result.ok
    return conn


def test_pending_queue_and_approval(ready):
    rows = review.pending(ready)
    assert len(rows) == 1 and rows[0]["id"] == 1
    review.approve(ready, 1, note="ok")
    assert review.pending(ready) == []
    status = ready.execute("SELECT review_status FROM renders WHERE id=1").fetchone()[0]
    assert status == "approved"


def test_reject_requires_note(ready):
    with pytest.raises(ValueError, match="motif"):
        review.reject(ready, 1, "  ")
    review.reject(ready, 1, "hook trop mou")
    assert review.pending(ready) == []


def test_publish_requires_g4_approval(ready):
    with pytest.raises(ValueError, match="G4"):
        publish_render(ready, 1, DryRunPublisher(), ["tiktok"], "@compte")


def test_publish_multi_platform_and_duplicate_lock(ready):
    review.approve(ready, 1)
    results = publish_render(
        ready, 1, DryRunPublisher(), ["tiktok", "instagram", "youtube"], "@compte"
    )
    assert [r.platform for r in results] == ["tiktok", "instagram", "youtube"]
    assert ready.execute("SELECT COUNT(*) FROM publications").fetchone()[0] == 3

    # même fichier, même plateforme, même compte → refus (règle d'or)
    with pytest.raises(ValueError, match="doublon"):
        publish_render(ready, 1, DryRunPublisher(), ["tiktok"], "@compte")
    # autre compte → autorisé
    publish_render(ready, 1, DryRunPublisher(), ["tiktok"], "@autre")
    assert ready.execute("SELECT COUNT(*) FROM publications").fetchone()[0] == 4


def test_publish_rejects_unknown_platform_and_g3_blocked(ready):
    review.approve(ready, 1)
    with pytest.raises(ValueError, match="plateforme"):
        publish_render(ready, 1, DryRunPublisher(), ["twitter"], "@c")
    ready.execute("UPDATE renders SET ok=0 WHERE id=1")
    with pytest.raises(ValueError, match="G3"):
        publish_render(ready, 1, DryRunPublisher(), ["tiktok"], "@c")


def test_metrics_and_stats(ready):
    review.approve(ready, 1)
    publish_render(ready, 1, DryRunPublisher(), ["tiktok", "instagram"], "@compte")

    telemetry.record(ready, 1, 24, views=1200, likes=80)
    telemetry.record(ready, 1, 72, views=15000, proof_path="proofs/p1.png")
    telemetry.record(ready, 2, 24, views=300)
    # écrasement idempotent du même relevé
    telemetry.record(ready, 2, 24, views=450)

    with pytest.raises(ValueError, match="échéance"):
        telemetry.record(ready, 1, 48, views=1)
    with pytest.raises(ValueError, match="inconnue"):
        telemetry.record(ready, 99, 24, views=1)

    stats = telemetry.compute_stats(ready)
    assert stats.publications == 2
    # dernier relevé par publication : 15000 (tiktok @72h) + 450 (instagram @24h)
    assert stats.views_by_platform == {"tiktok": 15000, "instagram": 450}
    assert stats.views_by_source == {"Podcast X": 15450}
    assert stats.approval_rate == 1.0
    assert stats.g2_pass_rate == 1.0
