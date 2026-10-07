from __future__ import annotations

DEFAULT_WEIGHTS = {
    "follower_ratio": 0.15,
    "engagement_rate": 0.30,
    "video_count": 0.10,
    "growth_trend": 0.25,
    "consistency": 0.20,
}
DEFAULT_THRESHOLDS = {"healthy": 70, "warning": 40}


def compute_follower_ratio_score(followers: int, following: int) -> float:
    if followers == 0 and following == 0:
        return 50.0
    if following == 0:
        return 100.0
    ratio = followers / following
    if ratio >= 10:
        return 100.0
    if ratio >= 3:
        return 80.0
    if ratio >= 1:
        return 60.0
    if ratio >= 0.5:
        return 40.0
    return 20.0


def compute_engagement_score(total_likes: int, video_count: int, followers: int) -> float:
    if video_count == 0 or followers == 0:
        return 30.0
    avg_likes = total_likes / video_count
    rate = avg_likes / followers
    if rate >= 0.10:
        return 100.0
    if rate >= 0.05:
        return 85.0
    if rate >= 0.02:
        return 70.0
    if rate >= 0.01:
        return 50.0
    if rate >= 0.005:
        return 35.0
    return 15.0


def compute_video_count_score(video_count: int) -> float:
    if video_count >= 50:
        return 100.0
    if video_count >= 20:
        return 80.0
    if video_count >= 10:
        return 60.0
    if video_count >= 3:
        return 40.0
    return 20.0


def compute_growth_score(current: int, previous: int | None) -> float:
    if previous is None or previous == 0:
        return 50.0
    change = (current - previous) / previous
    if change >= 0.10:
        return 100.0
    if change >= 0.03:
        return 80.0
    if change >= 0.0:
        return 60.0
    if change >= -0.05:
        return 40.0
    return 10.0


def compute_consistency_score(scores: list[float]) -> float:
    if len(scores) < 2:
        return 50.0
    diffs = [abs(scores[i] - scores[i - 1]) for i in range(1, len(scores))]
    avg = sum(diffs) / len(diffs)
    if avg <= 5:
        return 100.0
    if avg <= 10:
        return 80.0
    if avg <= 20:
        return 60.0
    if avg <= 30:
        return 40.0
    return 20.0


def score_health(
    followers: int,
    following: int,
    total_likes: int,
    video_count: int,
    previous_followers: int | None = None,
    recent_scores: list[float] | None = None,
    weights: dict[str, float] | None = None,
    thresholds: dict[str, int] | None = None,
) -> dict:
    w = weights or DEFAULT_WEIGHTS
    t = thresholds or DEFAULT_THRESHOLDS
    sub = {
        "follower_ratio": compute_follower_ratio_score(followers, following),
        "engagement_rate": compute_engagement_score(total_likes, video_count, followers),
        "video_count": compute_video_count_score(video_count),
        "growth_trend": compute_growth_score(followers, previous_followers),
        "consistency": compute_consistency_score(recent_scores or []),
    }
    total = sum(sub[k] * w.get(k, 0) for k in sub)
    total = round(min(100.0, max(0.0, total)), 1)
    if total >= t["healthy"]:
        level = "healthy"
    elif total >= t["warning"]:
        level = "warning"
    else:
        level = "critical"
    return {"score": total, "level": level, "breakdown": sub}
