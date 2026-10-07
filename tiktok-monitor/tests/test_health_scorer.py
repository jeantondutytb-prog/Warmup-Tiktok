from app.core.health_scorer import (
    compute_follower_ratio_score,
    compute_engagement_score,
    compute_video_count_score,
    compute_growth_score,
    compute_consistency_score,
    score_health,
)


def test_follower_ratio_high():
    assert compute_follower_ratio_score(10000, 500) >= 80


def test_follower_ratio_low():
    assert compute_follower_ratio_score(50, 500) <= 40


def test_follower_ratio_zero_zero():
    assert compute_follower_ratio_score(0, 0) == 50.0


def test_follower_ratio_no_following():
    assert compute_follower_ratio_score(1000, 0) == 100.0


def test_engagement_high():
    assert compute_engagement_score(50000, 10, 5000) >= 80


def test_engagement_low():
    assert compute_engagement_score(100, 100, 10000) <= 35


def test_engagement_no_videos():
    assert compute_engagement_score(0, 0, 1000) == 30.0


def test_video_count_many():
    assert compute_video_count_score(60) == 100.0


def test_video_count_few():
    assert compute_video_count_score(2) == 20.0


def test_growth_positive():
    assert compute_growth_score(1100, 1000) >= 60


def test_growth_negative():
    assert compute_growth_score(800, 1000) <= 40


def test_growth_no_previous():
    assert compute_growth_score(1000, None) == 50.0


def test_consistency_stable():
    assert compute_consistency_score([75, 76, 74, 77]) >= 80


def test_consistency_volatile():
    assert compute_consistency_score([30, 80, 20, 90]) <= 40


def test_consistency_single():
    assert compute_consistency_score([75]) == 50.0


def test_score_health_healthy():
    result = score_health(
        followers=5000, following=500,
        total_likes=100000, video_count=30,
        previous_followers=4500,
        recent_scores=[75, 76, 74],
    )
    assert result["level"] == "healthy"
    assert result["score"] >= 70
    assert "breakdown" in result


def test_score_health_critical():
    result = score_health(
        followers=10, following=500,
        total_likes=0, video_count=1,
        previous_followers=100,
    )
    assert result["level"] == "critical"
    assert result["score"] < 40


def test_score_health_custom_weights():
    result = score_health(
        followers=1000, following=100,
        total_likes=5000, video_count=10,
        weights={"follower_ratio": 1.0, "engagement_rate": 0, "video_count": 0, "growth_trend": 0, "consistency": 0},
    )
    assert result["score"] == compute_follower_ratio_score(1000, 100)


def test_score_health_custom_thresholds():
    result = score_health(
        followers=1000, following=500,
        total_likes=5000, video_count=10,
        thresholds={"healthy": 90, "warning": 50},
    )
    assert result["level"] in ("healthy", "warning", "critical")
