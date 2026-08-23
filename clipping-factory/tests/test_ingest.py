from pathlib import Path

import pytest

from factory import db, ingest

FIXTURES = Path(__file__).parent / "fixtures"
FEED_XML = (FIXTURES / "podcast_feed.xml").read_text(encoding="utf-8")


@pytest.fixture
def conn(tmp_path):
    return db.connect(str(tmp_path / "test.db"))


def test_parse_feed():
    episodes = ingest.parse_feed(FEED_XML)
    assert len(episodes) == 2  # l'item sans enclosure est ignoré
    assert episodes[0].guid == "ep-42"
    assert episodes[0].duration_s == 3750.0   # 1:02:30
    assert episodes[1].duration_s == 3600.0   # secondes brutes


def test_add_source_requires_authorization(conn):
    with pytest.raises(ValueError):
        ingest.add_source(
            conn, kind="podcast_rss", name="X", language="fr",
            authorization_kind="written", authorization_proof="   ",
        )
    with pytest.raises(ValueError):
        ingest.add_source(
            conn, kind="podcast_rss", name="X", language="fr",
            authorization_kind="tolérée", authorization_proof="email",
        )


def test_scan_registers_new_episodes_once(conn):
    ingest.add_source(
        conn, kind="podcast_rss", name="Podcast Test FR", language="fr",
        authorization_kind="written", authorization_proof="email du 2026-08-01",
        feed_url="https://example.com/feed.xml",
    )
    report = ingest.scan_sources(conn, fetch=lambda url: FEED_XML)
    assert report == {"sources": 1, "episodes_new": 2, "errors": 0}
    # re-scan : rien de nouveau
    report = ingest.scan_sources(conn, fetch=lambda url: FEED_XML)
    assert report["episodes_new"] == 0


def test_fetch_audio_updates_status(conn, tmp_path):
    ingest.add_source(
        conn, kind="podcast_rss", name="P", language="fr",
        authorization_kind="written", authorization_proof="email",
        feed_url="https://example.com/feed.xml",
    )
    ingest.scan_sources(conn, fetch=lambda url: FEED_XML)
    path = ingest.fetch_audio(
        conn, 1, tmp_path / "media", fetch_bytes=lambda url: b"FAKEMP3"
    )
    assert path.read_bytes() == b"FAKEMP3"
    row = conn.execute("SELECT status, audio_path FROM episodes WHERE id=1").fetchone()
    assert row["status"] == "fetched"
    assert row["audio_path"] == str(path)


def test_feed_error_counted_not_fatal(conn):
    ingest.add_source(
        conn, kind="podcast_rss", name="Cassé", language="fr",
        authorization_kind="written", authorization_proof="email",
        feed_url="https://broken.example.com/feed.xml",
    )

    def broken_fetch(url):
        raise OSError("réseau")

    report = ingest.scan_sources(conn, fetch=broken_fetch)
    assert report["errors"] == 1
