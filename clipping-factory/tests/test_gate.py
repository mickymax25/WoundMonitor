from datetime import timedelta

from factory.config import RadarConfig
from factory.models import Campaign, utcnow
from factory.radar.gate import evaluate, score

CFG = RadarConfig()


def make(**kwargs) -> Campaign:
    base = dict(
        source="test",
        external_id="c1",
        name="Campagne test",
        currency="USD",
        cpm=2.0,
        budget_total=1000.0,
        budget_remaining=900.0,
        platforms=("tiktok",),
    )
    base.update(kwargs)
    return Campaign(**base)


def test_passes_nominal_campaign():
    result = evaluate(make(), CFG)
    assert result.passed
    assert result.score is not None and result.score > 50


def test_rejects_drained_budget():
    result = evaluate(make(budget_remaining=100.0), CFG)
    assert not result.passed
    assert any("budget restant" in r for r in result.reasons)


def test_rejects_low_cpm_and_unknown_cpm():
    assert not evaluate(make(cpm=0.3), CFG).passed
    result = evaluate(make(cpm=None), CFG)
    assert not result.passed
    assert "CPM inconnu" in result.reasons


def test_eur_threshold_is_lower():
    assert evaluate(make(currency="EUR", cpm=0.5), CFG).passed
    assert not evaluate(make(currency="USD", cpm=0.5), CFG).passed


def test_rejects_excluded_categories():
    result = evaluate(make(description="clip the biggest casino wins"), CFG)
    assert not result.passed
    assert any("catégorie exclue" in r for r in result.reasons)


def test_rejects_unserved_platforms_and_audience():
    assert not evaluate(make(platforms=("twitter",)), CFG).passed
    result = evaluate(make(audience_requirements={"JP": 0.8}), CFG)
    assert not result.passed
    # une exigence sur un pays servi passe, même élevée
    assert evaluate(make(audience_requirements={"US": 0.8}), CFG).passed


def test_freshness_dominates_score():
    now = utcnow()
    fresh = make()
    stale = make(external_id="c2")
    stale.first_seen_at = now - timedelta(hours=CFG.freshness_window_hours + 1)
    assert score(fresh, CFG, now) > score(stale, CFG, now)


def test_score_bounds():
    now = utcnow()
    s = score(make(cpm=100.0), CFG, now)
    assert 0.0 <= s <= 100.0
