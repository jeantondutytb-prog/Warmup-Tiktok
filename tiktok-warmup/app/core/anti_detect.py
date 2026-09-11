import random
import math
from datetime import datetime


def human_delay(min_s: float = 0.5, max_s: float = 2.0) -> float:
    mean = (min_s + max_s) / 2
    std = (max_s - min_s) / 4
    delay = random.gauss(mean, std)
    return max(min_s, min(max_s, delay))


def should_micro_pause(probability: float = 0.05) -> float:
    if random.random() < probability:
        return random.uniform(5.0, 15.0)
    return 0.0


def session_duration_seconds() -> int:
    mean = 1800
    std = 450
    duration = int(random.gauss(mean, std))
    return max(900, min(2700, duration))


_RAMP_UP_SCHEDULE = {
    (1, 2): ["scroll", "watch"],
    (3, 4): ["scroll", "watch", "like"],
    (5, 7): ["scroll", "watch", "like", "follow", "visit_profile"],
    (8, 10): ["scroll", "watch", "like", "follow", "visit_profile", "comment"],
}
_ALL_ACTIONS = ["scroll", "watch", "like", "follow", "visit_profile", "comment"]


def get_allowed_actions(ramp_up_day: int) -> list[str]:
    if ramp_up_day >= 11:
        return list(_ALL_ACTIONS)
    for (start, end), actions in _RAMP_UP_SCHEDULE.items():
        if start <= ramp_up_day <= end:
            return list(actions)
    return ["scroll", "watch"]


def get_action_limits(ramp_up_day: int) -> dict[str, int]:
    if ramp_up_day <= 2:
        return {"scroll": 999, "watch": 999, "like": 0, "follow": 0, "visit_profile": 0, "comment": 0}
    if ramp_up_day <= 4:
        likes = random.randint(5, 10)
        return {"scroll": 999, "watch": 999, "like": likes, "follow": 0, "visit_profile": 0, "comment": 0}
    if ramp_up_day <= 7:
        likes = random.randint(5, 10)
        follows = random.randint(1, 3)
        return {"scroll": 999, "watch": 999, "like": likes, "follow": follows, "visit_profile": follows + 2, "comment": 0}
    if ramp_up_day <= 10:
        likes = random.randint(8, 15)
        follows = random.randint(1, 3)
        comments = random.randint(1, 2)
        return {"scroll": 999, "watch": 999, "like": likes, "follow": follows, "visit_profile": follows + 2, "comment": comments}
    likes = random.randint(10, 20)
    follows = random.randint(1, 5)
    comments = random.randint(2, 5)
    return {"scroll": 999, "watch": 999, "like": likes, "follow": follows, "visit_profile": follows + 3, "comment": comments}


def is_in_activity_window(hour_start: int = 7, hour_end: int = 24) -> bool:
    return hour_start <= datetime.now().hour < hour_end


def pick_comment(comments: dict[str, list[str]], style: str, used_today: set[str]) -> str:
    pool = comments.get(style, comments.get("casual", []))
    available = [c for c in pool if c not in used_today]
    if not available:
        available = pool
    base = random.choice(available)
    return _apply_variation(base)


def _apply_variation(text: str) -> str:
    variations = [
        lambda t: t,
        lambda t: t + " " + random.choice(["🔥", "❤️", "😂", "💯", "👏", "✨"]),
        lambda t: t.lower(),
        lambda t: t + "!",
        lambda t: t + "!!",
        lambda t: t.rstrip("!") + " !",
    ]
    return random.choice(variations)(text)


def should_like(like_rate: float = 0.15) -> bool:
    return random.random() < like_rate


def watch_duration(video_length: int = 15) -> int:
    r = random.random()
    if r < 0.45:
        return random.randint(2, 4)
    elif r < 0.75:
        return random.randint(4, min(8, video_length))
    elif r < 0.90:
        return random.randint(7, min(15, video_length))
    elif r < 0.98:
        return random.randint(12, min(20, video_length + 3))
    else:
        return random.randint(15, min(30, video_length + 5))
