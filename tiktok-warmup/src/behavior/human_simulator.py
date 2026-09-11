"""Simulateur de comportement humain — délais, swipes et probabilités."""

from __future__ import annotations

import random
import time
from dataclasses import dataclass

import numpy as np


@dataclass
class WarmupProfile:
    name: str
    description: str
    min_watch_seconds: float
    max_watch_seconds: float
    like_probability: float
    follow_probability: float
    comment_probability: float
    profile_visit_probability: float
    scroll_back_probability: float
    pause_probability: float
    session_duration_minutes: int
    max_videos_per_session: int


@dataclass
class HumanBehaviorConfig:
    swipe_duration_min: int
    swipe_duration_max: int
    swipe_distance_variance: float
    micro_pause_min: int
    micro_pause_max: int
    between_action_delay_min: int
    between_action_delay_max: int
    session_break_min: int
    session_break_max: int


class HumanSimulator:
    """Génère des timings et décisions aléatoires mais réalistes."""

    def __init__(self, profile: WarmupProfile, behavior: HumanBehaviorConfig):
        self.profile = profile
        self.behavior = behavior
        self._rng = random.Random()

    def watch_duration(self) -> float:
        """Durée de visionnage avec distribution gaussienne biaisée vers le milieu."""
        low, high = self.profile.min_watch_seconds, self.profile.max_watch_seconds
        mean = (low + high) / 2
        std = (high - low) / 4
        duration = np.random.normal(mean, std)
        return float(np.clip(duration, low, high))

    def should_like(self) -> bool:
        return self._chance(self.profile.like_probability)

    def should_follow(self) -> bool:
        return self._chance(self.profile.follow_probability)

    def should_comment(self) -> bool:
        return self._chance(self.profile.comment_probability)

    def should_visit_profile(self) -> bool:
        return self._chance(self.profile.profile_visit_probability)

    def should_scroll_back(self) -> bool:
        return self._chance(self.profile.scroll_back_probability)

    def should_pause(self) -> bool:
        return self._chance(self.profile.pause_probability)

    def swipe_duration_ms(self) -> int:
        return self._rng.randint(
            self.behavior.swipe_duration_min, self.behavior.swipe_duration_max
        )

    def swipe_end_offset(self, base_y: float, screen_height: float) -> tuple[float, float]:
        """Calcule les coordonnées de fin de swipe avec variance naturelle."""
        variance = self.behavior.swipe_distance_variance
        start_x = 0.5 + self._rng.uniform(-0.03, 0.03)
        start_y = base_y + self._rng.uniform(-variance, variance) * 0.1
        end_x = start_x + self._rng.uniform(-0.02, 0.02)
        end_y = self._rng.uniform(0.15, 0.35)
        return (start_x, start_y, end_x, end_y)

    def between_actions_delay(self) -> float:
        ms = self._rng.randint(
            self.behavior.between_action_delay_min,
            self.behavior.between_action_delay_max,
        )
        return ms / 1000.0

    def micro_pause(self) -> float:
        ms = self._rng.randint(
            self.behavior.micro_pause_min, self.behavior.micro_pause_max
        )
        return ms / 1000.0

    def pause_duration(self) -> float:
        """Pause longue simulant la lecture de commentaires ou la réflexion."""
        return self._rng.uniform(2.0, 8.0)

    def session_break_duration(self) -> float:
        minutes = self._rng.randint(
            self.behavior.session_break_min, self.behavior.session_break_max
        )
        return minutes * 60.0

    def human_sleep(self, seconds: float) -> None:
        """Sommeil avec micro-variations pour éviter des patterns réguliers."""
        jitter = self._rng.uniform(-0.05, 0.05) * seconds
        time.sleep(max(0.1, seconds + jitter))

    def _chance(self, probability: float) -> bool:
        return self._rng.random() < probability
