"""Actions TikTok sur iOS via Appium — swipe, like, follow, etc."""

from __future__ import annotations

import logging
import subprocess
from typing import TYPE_CHECKING

from appium.webdriver.common.appiumby import AppiumBy
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

if TYPE_CHECKING:
    from appium.webdriver.webdriver import WebDriver

    from src.behavior.human_simulator import HumanSimulator

logger = logging.getLogger("tiktok-warmup")


class TikTokActions:
    """Couche d'interaction bas niveau avec l'app TikTok."""

    # Sélecteurs iOS — TikTok change souvent son UI, ces XPath sont des fallbacks
    LIKE_BUTTON_ACCESSIBILITY = "Like"
    FOLLOW_BUTTON_ACCESSIBILITY = "Follow"
    COMMENT_BUTTON_ACCESSIBILITY = "Comment"

    def __init__(self, driver: WebDriver, simulator: HumanSimulator):
        self.driver = driver
        self.sim = simulator
        self._screen_size: tuple[int, int] | None = None

    @property
    def screen_size(self) -> tuple[int, int]:
        if self._screen_size is None:
            size = self.driver.get_window_size()
            self._screen_size = (size["width"], size["height"])
        return self._screen_size

    def launch_tiktok(self, bundle_id: str) -> None:
        """Active TikTok s'il tourne déjà, sinon le lance."""
        logger.info("Lancement de TikTok (%s)...", bundle_id)
        try:
            self.driver.activate_app(bundle_id)
        except Exception:
            self.driver.execute_script("mobile: launchApp", {"bundleId": bundle_id})

        self.sim.human_sleep(3.0)
        self._dismiss_popups()

    def _dismiss_popups(self) -> None:
        """Ferme les popups courants (notifications, mises à jour, etc.)."""
        dismiss_labels = ["Not Now", "Skip", "Close", "OK", "Cancel", "Later"]
        for label in dismiss_labels:
            try:
                btn = self.driver.find_element(AppiumBy.ACCESSIBILITY_ID, label)
                btn.click()
                self.sim.human_sleep(0.5)
            except NoSuchElementException:
                continue

    def swipe_next_video(self) -> None:
        """Swipe vers le haut pour passer à la vidéo suivante."""
        w, h = self.screen_size
        _, start_y_norm, end_x_norm, end_y_norm = self.sim.swipe_end_offset(0.75, h)
        start_x = int(w * 0.5)
        start_y = int(h * start_y_norm)
        end_x = int(w * end_x_norm)
        end_y = int(h * end_y_norm)
        duration = self.sim.swipe_duration_ms()

        self.driver.execute_script(
            "mobile: dragFromToForDuration",
            {
                "duration": duration / 1000.0,
                "fromX": start_x,
                "fromY": start_y,
                "toX": end_x,
                "toY": end_y,
            },
        )
        logger.debug("Swipe next (%dms)", duration)

    def swipe_previous_video(self) -> None:
        """Swipe vers le bas pour revenir à la vidéo précédente."""
        w, h = self.screen_size
        start_x = int(w * 0.5)
        start_y = int(h * 0.25)
        end_x = start_x + self.sim._rng.randint(-10, 10)
        end_y = int(h * 0.75)
        duration = self.sim.swipe_duration_ms()

        self.driver.execute_script(
            "mobile: dragFromToForDuration",
            {
                "duration": duration / 1000.0,
                "fromX": start_x,
                "fromY": start_y,
                "toX": end_x,
                "toY": end_y,
            },
        )
        logger.debug("Swipe back")

    def tap_like(self) -> bool:
        """Double-tap au centre (like natif TikTok) ou bouton like."""
        w, h = self.screen_size
        try:
            like_btn = self.driver.find_element(
                AppiumBy.ACCESSIBILITY_ID, self.LIKE_BUTTON_ACCESSIBILITY
            )
            like_btn.click()
            logger.info("Like via bouton")
            return True
        except NoSuchElementException:
            center_x = int(w * 0.5)
            center_y = int(h * 0.45)
            self.driver.tap([(center_x, center_y)], 100)
            self.sim.human_sleep(0.15)
            self.driver.tap([(center_x, center_y)], 100)
            logger.info("Like via double-tap")
            return True

    def tap_follow(self) -> bool:
        try:
            follow_btn = WebDriverWait(self.driver, 3).until(
                EC.presence_of_element_located(
                    (AppiumBy.ACCESSIBILITY_ID, self.FOLLOW_BUTTON_ACCESSIBILITY)
                )
            )
            follow_btn.click()
            logger.info("Follow")
            return True
        except (NoSuchElementException, TimeoutException):
            logger.debug("Bouton Follow non trouvé")
            return False

    def visit_profile_and_back(self) -> bool:
        """Tap sur l'avatar créateur puis retour."""
        w, h = self.screen_size
        avatar_x = int(w * 0.92)
        avatar_y = int(h * 0.55)

        try:
            self.driver.tap([(avatar_x, avatar_y)])
            self.sim.human_sleep(self.sim.pause_duration())

            back_btn = self.driver.find_element(AppiumBy.ACCESSIBILITY_ID, "Back")
            back_btn.click()
            logger.info("Visite profil + retour")
            return True
        except NoSuchElementException:
            self._go_back()
            return False

    def _go_back(self) -> None:
        try:
            self.driver.back()
        except Exception:
            w, h = self.screen_size
            self.driver.tap([(20, int(h * 0.08))])

    def is_tiktok_foreground(self, bundle_id: str) -> bool:
        try:
            state = self.driver.query_app_state(bundle_id)
            return state in (3, 4)  # running foreground / background
        except Exception:
            return True


def detect_ios_udid() -> str | None:
    """Détecte l'UDID de l'iPhone connecté via USB."""
    try:
        result = subprocess.run(
            ["idevice_id", "-l"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        udids = [u.strip() for u in result.stdout.strip().split("\n") if u.strip()]
        return udids[0] if udids else None
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
