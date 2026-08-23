import json
from pathlib import Path

import pytest

from factory import db, ingest
from factory.moments import (
    ClaudeScorer,
    HeuristicScorer,
    MomentCandidate,
    save_moments,
    _windows,
)
from factory.transcribe import (
    FixtureTranscriber,
    Segment,
    load_transcript,
    save_transcript,
    transcribe_episode,
)

FIXTURES = Path(__file__).parent / "fixtures"


def load_segments() -> list[Segment]:
    raw = json.loads((FIXTURES / "transcript_fr.json").read_text(encoding="utf-8"))
    return [Segment(**s) for s in raw]


def test_windows_respect_bounds():
    windows = _windows(load_segments())
    assert windows
    for w in windows:
        length = w[-1].end - w[0].start
        assert 20.0 <= length <= 60.0


def test_heuristic_ranks_hook_segment_first():
    scorer = HeuristicScorer()
    moments = scorer.find_moments(load_segments(), "fr", top_n=3)
    assert moments
    best = moments[0]
    # le passage "Tu sais pourquoi 90% ... secret" (100–141 s) doit dominer
    assert 90.0 <= best.t_start <= 110.0
    # et battre nettement le small talk du début et le passage restaurant
    others = [m for m in moments[1:]]
    for other in others:
        assert best.score >= other.score


def test_heuristic_moments_do_not_overlap():
    moments = HeuristicScorer().find_moments(load_segments(), "fr", top_n=5)
    for i, a in enumerate(moments):
        for b in moments[i + 1:]:
            assert a.t_start >= b.t_end or a.t_end <= b.t_start


def test_composite_score_weighting():
    c = MomentCandidate(
        t_start=0, t_end=30, title="t", hook=10, emotion=0, autonomy=0,
        justification="",
    )
    assert c.score == 4.0  # hook pèse 40 %


class _FakeParsed:
    def __init__(self, moments):
        self.parsed_output = type("S", (), {"moments": moments})()


class _FakeMessages:
    def __init__(self, moments):
        self._moments = moments
        self.last_kwargs = None

    def parse(self, **kwargs):
        self.last_kwargs = kwargs
        return _FakeParsed(self._moments)


class _FakeClient:
    def __init__(self, moments):
        self.messages = _FakeMessages(moments)


def _llm_moment(**overrides):
    base = dict(
        start_s=100.0, end_s=141.0, title="Le secret des créateurs",
        hook=9.0, emotion=8.0, autonomy=8.5,
        justification="Accroche forte et chiffres concrets.",
    )
    base.update(overrides)
    return type("M", (), base)()


def test_claude_scorer_clamps_and_filters():
    fake = _FakeClient([
        _llm_moment(),
        _llm_moment(start_s=0.0, end_s=5.0),          # trop court → écarté
        _llm_moment(start_s=100.0, end_s=250.0),      # trop long → écarté
        _llm_moment(hook=42.0, start_s=280.0, end_s=500.0),  # clampé fin d'audio + /10
    ])
    scorer = ClaudeScorer(model="claude-opus-5", client=fake)
    moments = scorer.find_moments(load_segments(), "fr", top_n=5)
    assert len(moments) == 2
    assert moments[0].t_start == 100.0 and moments[0].t_end == 141.0
    clamped = moments[1]
    assert clamped.hook == 10.0
    assert clamped.t_end == 334.0  # borné à la fin du transcript
    # le transcript horodaté est bien passé au modèle
    prompt = fake.messages.last_kwargs["messages"][0]["content"]
    assert "[100.0–108.0]" in prompt


def _episode_ready(tmp_path):
    conn = db.connect(str(tmp_path / "test.db"))
    ingest.add_source(
        conn, kind="podcast_rss", name="P", language="fr",
        authorization_kind="written", authorization_proof="email",
        feed_url="https://example.com/feed.xml",
    )
    feed = (FIXTURES / "podcast_feed.xml").read_text(encoding="utf-8")
    ingest.scan_sources(conn, fetch=lambda url: feed)
    ingest.fetch_audio(conn, 1, tmp_path / "media", fetch_bytes=lambda url: b"x")
    return conn


def test_transcribe_then_save_moments_full_flow(tmp_path):
    conn = _episode_ready(tmp_path)
    transcriber = FixtureTranscriber(load_segments())
    path = transcribe_episode(conn, 1, transcriber, tmp_path / "media")
    assert load_transcript(path)[0].text.startswith("Bienvenue")
    assert conn.execute("SELECT status FROM episodes WHERE id=1").fetchone()[0] == "transcribed"

    moments = HeuristicScorer().find_moments(load_segments(), "fr")
    passed = save_moments(conn, 1, moments, "heuristic")
    rows = conn.execute("SELECT * FROM moments ORDER BY score DESC").fetchall()
    assert len(rows) == len(moments)
    assert passed == sum(r["g2_passed"] for r in rows)
    assert conn.execute("SELECT status FROM episodes WHERE id=1").fetchone()[0] == "scored"

    # rejouer S3 remplace les moments au lieu de les dupliquer
    save_moments(conn, 1, moments, "heuristic")
    assert conn.execute("SELECT COUNT(*) FROM moments").fetchone()[0] == len(moments)


def test_save_transcript_roundtrip(tmp_path):
    path = tmp_path / "t.json"
    save_transcript(load_segments(), path)
    assert [s.text for s in load_transcript(path)] == [s.text for s in load_segments()]


def test_g2_threshold_env(monkeypatch, tmp_path):
    conn = _episode_ready(tmp_path)
    moments = [
        MomentCandidate(t_start=0, t_end=30, title="a", hook=8, emotion=8,
                        autonomy=8, justification=""),   # score 8.0
        MomentCandidate(t_start=40, t_end=70, title="b", hook=5, emotion=5,
                        autonomy=5, justification=""),   # score 5.0
    ]
    monkeypatch.setenv("G2_MIN_SCORE", "6.0")
    assert save_moments(conn, 1, moments, "test") == 1
    monkeypatch.setenv("G2_MIN_SCORE", "4.0")
    assert save_moments(conn, 1, moments, "test") == 2
