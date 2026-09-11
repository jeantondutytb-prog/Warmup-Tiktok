import random
from datetime import datetime, timedelta

import pytest

from app.core.protocol import (
    FOLLOWS_PER_SESSION,
    FOLLOW_PER_HOUR,
    MIN_GAP_BETWEEN_ACCOUNTS,
    MIN_GAP_SAME_ACCOUNT,
    PHASES,
    SESSION_SECONDS,
    SessionBudget,
    can_start_session,
    daily_cap,
    flatten_keywords,
    follow_rate_ok,
    fyp_verdict,
    keyword_for_session,
    phase_at,
    sessions_allowed_today,
    should_like_in_search,
    should_replay,
)

KEYWORDS = {
    "fr": ["filtre digicam", "effet appareil photo numérique"],
    "en": ["digicam filter", "g7x filter"],
}


# ---------------------------------------------------------------- phases

def test_phases_are_contiguous_and_fill_the_session():
    assert PHASES[0].start_s == 0
    for earlier, later in zip(PHASES, PHASES[1:]):
        assert earlier.end_s == later.start_s
    assert PHASES[-1].end_s == SESSION_SECONDS


def test_phase_at_maps_the_documented_timestamps():
    assert phase_at(0).name == "fyp_entry"
    assert phase_at(119).name == "fyp_entry"
    assert phase_at(120).name == "search"
    assert phase_at(599).name == "search"
    assert phase_at(600).name == "profiles"
    assert phase_at(780).name == "fyp_measure"


def test_phase_at_returns_none_once_the_session_is_over():
    assert phase_at(SESSION_SECONDS) is None
    assert phase_at(SESSION_SECONDS + 1) is None


# ---------------------------------------------------------------- plafonds

def test_daily_cap_stays_in_the_documented_range():
    rng = random.Random(0)
    for _ in range(200):
        assert 10 <= daily_cap("follow", rng) <= 15
        assert 20 <= daily_cap("like", rng) <= 30
        assert 0 <= daily_cap("comment", rng) <= 3


def test_follow_rate_ok_blocks_at_the_hourly_limit():
    now = datetime(2026, 9, 3, 12, 0)
    recent = [now - timedelta(minutes=m) for m in range(FOLLOW_PER_HOUR)]
    assert not follow_rate_ok(recent, now)
    assert follow_rate_ok(recent[:-1], now)


def test_follow_rate_ignores_follows_older_than_an_hour():
    now = datetime(2026, 9, 3, 12, 0)
    old = [now - timedelta(hours=2, minutes=m) for m in range(20)]
    assert follow_rate_ok(old, now)


# ---------------------------------------------------------------- mots-clés

def test_flatten_puts_french_before_english():
    assert flatten_keywords(KEYWORDS)[:2] == KEYWORDS["fr"]


def test_keyword_rotates_one_per_session_and_cycles():
    seen = [keyword_for_session(KEYWORDS, i) for i in range(4)]
    assert len(set(seen)) == 4
    assert keyword_for_session(KEYWORDS, 4) == seen[0]


def test_keyword_raises_when_none_configured():
    with pytest.raises(ValueError):
        keyword_for_session({}, 0)


# ---------------------------------------------------------------- cadence

def test_two_sessions_during_ramp_then_one_in_maintenance():
    assert sessions_allowed_today(1) == 2
    assert sessions_allowed_today(7) == 2
    assert sessions_allowed_today(8) == 1


def _check(**overrides):
    base = dict(
        protocol_day=1,
        sessions_today=0,
        last_session_this_account=None,
        last_session_any_account=None,
        now=datetime(2026, 9, 3, 12, 0),
    )
    base.update(overrides)
    return can_start_session(**base)


def test_a_fresh_account_can_start():
    assert _check().ok


def test_protected_account_is_always_refused():
    result = _check(protected=True)
    assert not result.ok
    assert "protégé" in result.reason


def test_daily_quota_blocks_a_third_session():
    assert not _check(sessions_today=2).ok


def test_same_account_needs_four_hours():
    now = datetime(2026, 9, 3, 12, 0)
    too_soon = _check(last_session_this_account=now - MIN_GAP_SAME_ACCOUNT + timedelta(minutes=1))
    assert not too_soon.ok
    assert too_soon.retry_after is not None
    assert _check(last_session_this_account=now - MIN_GAP_SAME_ACCOUNT).ok


def test_another_account_needs_thirty_minutes_on_the_same_device():
    now = datetime(2026, 9, 3, 12, 0)
    too_soon = _check(last_session_any_account=now - MIN_GAP_BETWEEN_ACCOUNTS + timedelta(minutes=1))
    assert not too_soon.ok
    assert _check(last_session_any_account=now - MIN_GAP_BETWEEN_ACCOUNTS).ok


# ---------------------------------------------------------------- signaux

def test_replay_only_for_short_videos():
    assert should_replay(14)
    assert not should_replay(15)
    assert not should_replay(30)


def test_search_like_rate_stays_under_the_thirty_percent_pattern():
    rng = random.Random(1)
    hits = sum(should_like_in_search(rng) for _ in range(5000))
    assert 0.26 < hits / 5000 < 0.34


# ---------------------------------------------------------------- mesure FYP

def test_fyp_verdict_thresholds():
    assert fyp_verdict(0) == "cold"
    assert fyp_verdict(1) == "cold"
    assert fyp_verdict(2) == "warming"
    assert fyp_verdict(3) == "ready"
    assert fyp_verdict(7) == "ready"


# ---------------------------------------------------------------- budget

def _budget(**overrides):
    base = dict(like_cap=25, follow_cap=12, comment_cap=2)
    base.update(overrides)
    return SessionBudget(**base)


def test_budget_blocks_likes_at_the_daily_cap():
    b = _budget(like_cap=2)
    assert b.can_like()
    b.record_like()
    b.record_like()
    assert not b.can_like()


def test_budget_refuses_two_follows_in_a_row():
    b = _budget()
    assert b.can_follow()[0]
    b.record_follow()
    ok, reason = b.can_follow()
    assert not ok
    assert "d'affilée" in reason


def test_a_profile_visit_without_follow_clears_the_streak():
    b = _budget()
    b.record_follow()
    b.record_profile_visit(followed=False)
    assert b.can_follow()[0]


def test_budget_caps_follows_per_session():
    b = _budget()
    now = datetime(2026, 9, 3, 12, 0)
    for i in range(FOLLOWS_PER_SESSION):
        assert b.can_follow(now)[0]
        b.record_follow(now)
        b.record_profile_visit(followed=False)
    ok, reason = b.can_follow(now)
    assert not ok
    assert "cette session" in reason


def test_budget_respects_the_hourly_follow_rate():
    now = datetime(2026, 9, 3, 12, 0)
    b = _budget(follow_times=[now - timedelta(minutes=m) for m in range(FOLLOW_PER_HOUR)])
    ok, reason = b.can_follow(now)
    assert not ok
    assert "débit" in reason


def test_profiles_remaining_counts_down():
    b = _budget()
    assert b.profiles_remaining() == 3
    b.record_profile_visit()
    assert b.profiles_remaining() == 2
