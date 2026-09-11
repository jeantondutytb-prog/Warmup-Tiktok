"""Session de warmup — boucle principale avec phases progressives."""

from __future__ import annotations

import logging
import signal
import sys
from datetime import datetime, timezone
from pathlib import Path

import yaml

from src.behavior.actions import TikTokActions
from src.behavior.human_simulator import HumanBehaviorConfig, HumanSimulator, WarmupProfile
from src.device.ios_driver import IOSDriver
from src.utils.logger import SessionStats, setup_logger

logger = logging.getLogger("tiktok-warmup")


class WarmupSession:
    """Orchestre une session complète de warmup TikTok."""

    def __init__(
        self,
        profile_name: str = "observer",
        config_path: Path | None = None,
        log_dir: Path | None = None,
        session_duration_override: int = 0,
    ):
        self.config_path = config_path or Path(__file__).parent.parent.parent / "config" / "warmup_profiles.yaml"
        self.log_dir = log_dir or Path(__file__).parent.parent.parent / "logs"
        self.config = self._load_config()
        self.profile = self._load_profile(profile_name)
        self.behavior = self._load_behavior()
        self.simulator = HumanSimulator(self.profile, self.behavior)
        self.stats = SessionStats(profile_name)
        self._running = True
        self.session_duration_override = session_duration_override

        self.ios = IOSDriver(bundle_id=self.config["tiktok"]["bundle_id"])
        self.actions: TikTokActions | None = None

    def _load_config(self) -> dict:
        with open(self.config_path) as f:
            return yaml.safe_load(f)

    def _load_profile(self, name: str) -> WarmupProfile:
        profiles = self.config["profiles"]
        if name not in profiles:
            available = ", ".join(profiles.keys())
            raise ValueError(f"Profil '{name}' inconnu. Disponibles: {available}")
        p = profiles[name]
        return WarmupProfile(name=name, **p)

    def _load_behavior(self) -> HumanBehaviorConfig:
        b = self.config["human_behavior"]
        return HumanBehaviorConfig(
            swipe_duration_min=b["swipe_duration_ms"]["min"],
            swipe_duration_max=b["swipe_duration_ms"]["max"],
            swipe_distance_variance=b["swipe_distance_variance"],
            micro_pause_min=b["micro_pause_ms"]["min"],
            micro_pause_max=b["micro_pause_ms"]["max"],
            between_action_delay_min=b["between_action_delay_ms"]["min"],
            between_action_delay_max=b["between_action_delay_ms"]["max"],
            session_break_min=b["session_break_minutes"]["min"],
            session_break_max=b["session_break_minutes"]["max"],
        )

    def _setup_signal_handlers(self) -> None:
        def handle_stop(signum, frame):
            logger.warning("Arrêt demandé (signal %s)...", signum)
            self._running = False

        signal.signal(signal.SIGINT, handle_stop)
        signal.signal(signal.SIGTERM, handle_stop)

    def run(self) -> dict:
        """Lance la session de warmup. Retourne le résumé des stats."""
        self._setup_signal_handlers()
        logger.info("=== Session Warmup TikTok ===")
        logger.info("Profil: %s — %s", self.profile.name, self.profile.description)

        duration_min = (
            self.session_duration_override
            if self.session_duration_override > 0
            else self.profile.session_duration_minutes
        )
        max_videos = self.profile.max_videos_per_session
        bundle_id = self.config["tiktok"]["bundle_id"]

        try:
            driver = self.ios.connect()
            self.actions = TikTokActions(driver, self.simulator)
            self.actions.launch_tiktok(bundle_id)

            session_start = datetime.now(timezone.utc)
            videos_this_session = 0

            while self._running:
                elapsed_min = (datetime.now(timezone.utc) - session_start).total_seconds() / 60
                if elapsed_min >= duration_min:
                    logger.info("Durée de session atteinte (%.0f min)", elapsed_min)
                    break
                if videos_this_session >= max_videos:
                    logger.info("Limite de vidéos atteinte (%d)", max_videos)
                    break

                self._process_video()
                videos_this_session += 1

                if videos_this_session % 15 == 0 and self._running:
                    break_duration = self.simulator.session_break_duration()
                    logger.info("Pause session (%.0f sec)...", break_duration)
                    self.simulator.human_sleep(break_duration)

        except Exception as e:
            logger.error("Erreur session: %s", e)
            raise
        finally:
            self._save_stats()
            self.ios.disconnect()

        summary = self.stats.summary()
        logger.info("=== Fin de session ===")
        for key, val in summary.items():
            logger.info("  %s: %s", key, val)
        return summary

    def _process_video(self) -> None:
        assert self.actions is not None
        sim = self.simulator

        watch_time = sim.watch_duration()
        logger.info("Visionnage vidéo (%.1fs)...", watch_time)
        sim.human_sleep(watch_time)
        self.stats.record("watch", duration=watch_time)

        if sim.should_pause():
            pause = sim.pause_duration()
            logger.info("Pause réflexion (%.1fs)...", pause)
            sim.human_sleep(pause)
            self.stats.record("pause", duration=pause)

        if sim.should_like():
            sim.human_sleep(sim.between_actions_delay())
            self.actions.tap_like()
            self.stats.record("like")

        if sim.should_visit_profile():
            sim.human_sleep(sim.micro_pause())
            if self.actions.visit_profile_and_back():
                self.stats.record("profile_visit")

        if sim.should_follow():
            sim.human_sleep(sim.between_actions_delay())
            if self.actions.tap_follow():
                self.stats.record("follow")

        if sim.should_scroll_back():
            sim.human_sleep(sim.micro_pause())
            self.actions.swipe_previous_video()
            self.stats.record("scroll_back")
            sim.human_sleep(sim.watch_duration() * 0.5)

        sim.human_sleep(sim.between_actions_delay())
        self.actions.swipe_next_video()
        sim.human_sleep(sim.micro_pause())

    def _save_stats(self) -> None:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        path = self.log_dir / f"session_{self.profile.name}_{timestamp}.json"
        self.stats.save(path)
        logger.info("Stats sauvegardées: %s", path)


def list_profiles(config_path: Path | None = None) -> list[str]:
    path = config_path or Path(__file__).parent.parent.parent / "config" / "warmup_profiles.yaml"
    with open(path) as f:
        config = yaml.safe_load(f)
    return list(config["profiles"].keys())
