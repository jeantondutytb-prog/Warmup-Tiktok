"""Connexion Appium à l'iPhone physique via USB."""

from __future__ import annotations

import logging
import os
from typing import Any

from appium import webdriver
from appium.options.ios import XCUITestOptions

from src.behavior.actions import detect_ios_udid

logger = logging.getLogger("tiktok-warmup")


class IOSDriver:
    """Gère la connexion Appium + WebDriverAgent sur iPhone."""

    def __init__(
        self,
        server_url: str | None = None,
        udid: str | None = None,
        device_name: str = "iPhone",
        platform_version: str = "17.0",
        bundle_id: str = "com.zhiliaoapp.musically",
        wda_local_port: int = 8100,
    ):
        self.server_url = server_url or os.getenv(
            "APPIUM_SERVER_URL", "http://127.0.0.1:4723"
        )
        self.udid = udid or os.getenv("IOS_UDID") or detect_ios_udid()
        self.device_name = device_name or os.getenv("IOS_DEVICE_NAME", "iPhone")
        self.platform_version = platform_version or os.getenv(
            "IOS_PLATFORM_VERSION", "17.0"
        )
        self.bundle_id = bundle_id
        self.wda_local_port = int(os.getenv("WDA_LOCAL_PORT", wda_local_port))
        self.driver: webdriver.webdriver.WebDriver | None = None

    def connect(self, no_reset: bool = True) -> webdriver.webdriver.WebDriver:
        if not self.udid:
            raise RuntimeError(
                "Aucun iPhone détecté. Branchez votre iPhone en USB et vérifiez "
                "que 'idevice_id -l' retourne un UDID, ou définissez IOS_UDID dans .env"
            )

        logger.info("Connexion à iPhone %s via Appium...", self.udid[:8])

        options = XCUITestOptions()
        options.platform_name = "iOS"
        options.automation_name = "XCUITest"
        options.device_name = self.device_name
        options.platform_version = self.platform_version
        options.udid = self.udid
        options.bundle_id = self.bundle_id
        options.no_reset = no_reset
        options.new_command_timeout = 300
        options.wda_local_port = self.wda_local_port
        options.set_capability("wdaLaunchTimeout", 120000)
        options.set_capability("wdaConnectionTimeout", 120000)
        options.set_capability("usePrebuiltWDA", False)
        options.set_capability("shouldTerminateApp", False)

        self.driver = webdriver.Remote(self.server_url, options=options)
        logger.info("Connecté — session Appium démarrée")
        return self.driver

    def disconnect(self) -> None:
        if self.driver:
            try:
                self.driver.quit()
            except Exception as e:
                logger.warning("Erreur à la déconnexion: %s", e)
            finally:
                self.driver = None

    def get_capabilities_summary(self) -> dict[str, Any]:
        return {
            "server": self.server_url,
            "udid": self.udid,
            "device": self.device_name,
            "ios_version": self.platform_version,
            "bundle_id": self.bundle_id,
            "wda_port": self.wda_local_port,
        }
