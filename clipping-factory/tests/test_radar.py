import json
from pathlib import Path

from factory import db
from factory.config import Settings
from factory.radar.base import SourceUnavailable
from factory.radar.runner import run_scan
from factory.radar.whop import WhopSource, parse_campaigns

FIXTURES = Path(__file__).parent / "fixtures"


class FixtureSource:
    name = "fixture"

    def __init__(self, campaigns):
        self.campaigns = campaigns

    def fetch(self):
        return self.campaigns


class BrokenSource:
    name = "broken"

    def fetch(self):
        raise RuntimeError("boom")


def load_fixture_campaigns():
    payload = json.loads((FIXTURES / "whop_campaigns.json").read_text())
    return parse_campaigns(payload)


def test_parse_whop_fixture():
    campaigns = load_fixture_campaigns()
    assert len(campaigns) == 5
    ai = next(c for c in campaigns if c.external_id == "camp_fresh_ai")
    assert ai.cpm == 2.0
    assert ai.budget_remaining_ratio == 0.92
    assert ai.platforms == ("tiktok", "instagram", "youtube")


def test_scan_gates_and_persists(tmp_path):
    settings = Settings(db_path=str(tmp_path / "test.db"))
    conn = db.connect(settings.db_path)
    report = run_scan(conn, [FixtureSource(load_fixture_campaigns())], settings)

    assert report.seen == 5
    assert report.new == 5
    # passent G1 : camp_fresh_ai + camp_fr_podcast ; rejetés : budget épuisé,
    # casino (malgré CPM 12$), CPM 0.3.
    assert report.passed == 2

    passed = db.list_campaigns(conn, only_passed=True)
    assert {r["external_id"] for r in passed} == {"camp_fresh_ai", "camp_fr_podcast"}
    # classement par score décroissant
    scores = [r["score"] for r in passed]
    assert scores == sorted(scores, reverse=True)


def test_rescan_keeps_first_seen(tmp_path):
    settings = Settings(db_path=str(tmp_path / "test.db"))
    conn = db.connect(settings.db_path)
    campaigns = load_fixture_campaigns()
    run_scan(conn, [FixtureSource(campaigns)], settings)
    first = db.load_campaign(conn, "whop:camp_fresh_ai").first_seen_at

    report = run_scan(conn, [FixtureSource(load_fixture_campaigns())], settings)
    assert report.new == 0
    assert db.load_campaign(conn, "whop:camp_fresh_ai").first_seen_at == first


def test_broken_source_does_not_block_scan(tmp_path):
    settings = Settings(db_path=str(tmp_path / "test.db"))
    conn = db.connect(settings.db_path)
    report = run_scan(
        conn,
        [BrokenSource(), FixtureSource(load_fixture_campaigns())],
        settings,
    )
    assert report.seen == 5
    assert len(report.errors) == 1


def test_whop_without_key_is_unavailable(monkeypatch):
    monkeypatch.delenv("WHOP_API_KEY", raising=False)
    source = WhopSource(api_key=None)
    try:
        source.fetch()
        raise AssertionError("SourceUnavailable attendu")
    except SourceUnavailable:
        pass
