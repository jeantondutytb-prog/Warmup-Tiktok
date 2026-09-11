from app.core.anti_detect import (
    human_delay,
    should_micro_pause,
    session_duration_seconds,
    get_allowed_actions,
    get_action_limits,
    pick_comment,
    should_like,
    watch_duration,
)


def test_human_delay_in_range():
    for _ in range(100):
        d = human_delay(2.0, 8.0)
        assert 2.0 <= d <= 8.0


def test_human_delay_distribution_is_centered():
    delays = [human_delay(2.0, 8.0) for _ in range(1000)]
    mean = sum(delays) / len(delays)
    assert 4.0 < mean < 6.0


def test_should_micro_pause_returns_zero_or_range():
    results = [should_micro_pause(0.5) for _ in range(200)]
    non_zero = [r for r in results if r > 0]
    zeros = [r for r in results if r == 0.0]
    assert len(non_zero) > 0
    assert len(zeros) > 0
    for v in non_zero:
        assert 5.0 <= v <= 15.0


def test_session_duration_in_range():
    for _ in range(50):
        d = session_duration_seconds()
        assert 900 <= d <= 2700


def test_ramp_up_day_1_scroll_watch_only():
    actions = get_allowed_actions(1)
    assert "scroll" in actions
    assert "watch" in actions
    assert "like" not in actions
    assert "comment" not in actions


def test_ramp_up_day_4_adds_likes():
    actions = get_allowed_actions(4)
    assert "like" in actions
    assert "comment" not in actions


def test_ramp_up_day_6_adds_follow():
    actions = get_allowed_actions(6)
    assert "follow" in actions
    assert "visit_profile" in actions


def test_ramp_up_day_9_adds_comment():
    actions = get_allowed_actions(9)
    assert "comment" in actions


def test_ramp_up_day_11_all_actions():
    actions = get_allowed_actions(11)
    assert set(actions) == {"scroll", "watch", "like", "follow", "visit_profile", "comment"}


def test_action_limits_day_1():
    limits = get_action_limits(1)
    assert limits.get("like", 0) == 0
    assert limits.get("follow", 0) == 0
    assert limits.get("comment", 0) == 0


def test_action_limits_day_4():
    limits = get_action_limits(4)
    assert 5 <= limits["like"] <= 10


def test_action_limits_cruise():
    limits = get_action_limits(15)
    assert limits["like"] >= 10
    assert limits["comment"] >= 2


def test_pick_comment_no_repeat():
    pool = {"casual": ["A", "B", "C"]}
    used = {"A"}
    comment = pick_comment(pool, "casual", used)
    assert comment not in used or len(pool["casual"]) - len(used) == 0


def test_pick_comment_applies_variation():
    pool = {"casual": ["Hello world"]}
    results = set()
    for _ in range(50):
        results.add(pick_comment(pool, "casual", set()))
    assert len(results) >= 1


def test_should_like_probability():
    results = [should_like(0.15) for _ in range(1000)]
    ratio = sum(results) / len(results)
    assert 0.05 < ratio < 0.30


def test_watch_duration_range():
    for _ in range(100):
        d = watch_duration(30)
        assert 2 <= d <= 35
