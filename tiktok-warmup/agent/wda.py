"""Détection iPhone et démarrage de WebDriverAgent.

WDA ne peut pas vivre sur Vercel : il parle à l'iPhone en USB / Wi-Fi local.
L'agent le lance tout seul pour que le dashboard n'ait plus qu'à cliquer Start.
"""

from __future__ import annotations

import json
import os
import re
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request

DEFAULT_UDID = "00008020-000D0CE43A99002E"
DEFAULT_TEAM = "U284BGAVKL"
DEFAULT_BUNDLE = "com.jean.wda.runner"
DEFAULT_PROJECT = (
    "/Users/jean/.appium/node_modules/appium-xcuitest-driver/"
    "node_modules/appium-webdriveragent/WebDriverAgent.xcodeproj"
)
DEFAULT_DERIVED = (
    "/Users/jean/Library/Developer/Xcode/DerivedData/"
    "WebDriverAgent-entqkdybqjzegiahlgkxvxghpzdf"
)

# WDA imprime `ServerURLHere->http://x:8100<-ServerURLHere` au boot.
SERVER_URL_RE = re.compile(r"ServerURLHere->(https?://[^<\s]+)")


def parse_server_url(line: str) -> str | None:
    """Extrait l'URL WDA d'une ligne de log xcodebuild, ou None."""
    match = SERVER_URL_RE.search(line)
    if not match:
        return None
    return match.group(1).rstrip("/")


def probe_wda(url: str, timeout: float = 2.0) -> bool:
    """True si WDA répond ready sur /status."""
    try:
        req = urllib.request.Request(f"{url.rstrip('/')}/status")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
        return bool(data.get("value", {}).get("ready"))
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError, ValueError):
        return False


def build_xcodebuild_cmd(
    udid: str,
    *,
    project: str | None = None,
    derived_data: str | None = None,
    team: str | None = None,
    bundle: str | None = None,
    rebuild: bool = False,
) -> list[str]:
    """Commande xcodebuild pour lancer (ou reconstruire) WDA."""
    action = "build-for-testing" if rebuild else "test-without-building"
    return [
        "xcodebuild", action,
        "-project", project or os.environ.get("WDA_PROJECT", DEFAULT_PROJECT),
        "-scheme", "WebDriverAgentRunner",
        "-derivedDataPath", derived_data or os.environ.get("WDA_DERIVED_DATA", DEFAULT_DERIVED),
        "-destination", f"id={udid}",
        "-allowProvisioningUpdates",
        "IPHONEOS_DEPLOYMENT_TARGET=18.7",
        f"DEVELOPMENT_TEAM={team or os.environ.get('DEVELOPMENT_TEAM', DEFAULT_TEAM)}",
        "CODE_SIGN_IDENTITY=Apple Development",
        f"PRODUCT_BUNDLE_IDENTIFIER={bundle or os.environ.get('WDA_BUNDLE_ID', DEFAULT_BUNDLE)}",
        "GCC_TREAT_WARNINGS_AS_ERRORS=0",
        "COMPILER_INDEX_STORE_ENABLE=NO",
    ]


def list_iphone_udids() -> list[str]:
    """UDID des iPhones appairés et allumés, via `xcrun devicectl`."""
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as handle:
        tmp_path = handle.name
    try:
        subprocess.run(
            ["xcrun", "devicectl", "list", "devices", "--json-output", tmp_path],
            capture_output=True, text=True, timeout=15,
        )
        with open(tmp_path) as handle:
            data = json.load(handle)
    except (FileNotFoundError, json.JSONDecodeError, subprocess.TimeoutExpired, OSError):
        return []
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    found: list[str] = []
    for device in data.get("result", {}).get("devices", []):
        hw = device.get("hardwareProperties", {})
        conn = device.get("connectionProperties", {})
        props = device.get("deviceProperties", {})
        if (
            hw.get("deviceType") == "iPhone"
            and conn.get("pairingState") == "paired"
            and props.get("bootState") == "booted"
        ):
            udid = hw.get("udid")
            if udid:
                found.append(udid)
    return found


def preferred_udid() -> str | None:
    """UDID d'un iPhone allumé, sinon DEVICE_UDID si posé."""
    found = list_iphone_udids()
    env = os.environ.get("DEVICE_UDID")
    if env and env in found:
        return env
    if found:
        return found[0]
    return env or None


class WDASupervisor:
    """Garde WDA vivant : probe, iproxy, xcodebuild, lecture de ServerURLHere."""

    def __init__(self) -> None:
        self.url = os.environ.get("WDA_URL", "http://127.0.0.1:8100").rstrip("/")
        self.iphone = False
        self.ready = False
        self.message = "pas encore sondé"
        self._xcode: subprocess.Popen[str] | None = None
        self._iproxy: subprocess.Popen[str] | None = None

    def snapshot(self) -> dict:
        return {
            "iphone": self.iphone,
            "wdaReady": self.ready,
            "wdaUrl": self.url if self.ready else None,
            "message": self.message,
        }

    def refresh(self) -> dict:
        """Met à jour l'état sans forcément relancer xcodebuild."""
        udids = list_iphone_udids()
        self.iphone = bool(udids)
        if probe_wda(self.url):
            self.ready = True
            self.message = f"WDA prêt sur {self.url}"
            return self.snapshot()
        for candidate in _candidate_urls(self.url):
            if probe_wda(candidate):
                self.url = candidate
                os.environ["WDA_URL"] = candidate
                self.ready = True
                self.message = f"WDA prêt sur {candidate}"
                return self.snapshot()
        self.ready = False
        if not self.iphone:
            self.message = "iPhone introuvable — branche-le en USB, déverrouille-le"
        elif self._xcode and self._xcode.poll() is None:
            self.message = "WDA en cours de démarrage…"
        else:
            self.message = "iPhone vu, WDA pas encore joignable"
        return self.snapshot()

    def ensure(self, timeout: float = 120.0) -> str:
        """Rend WDA joignable ou lève. Met WDA_URL dans l'environnement."""
        state = self.refresh()
        if self.ready:
            return self.url
        if not self.iphone:
            raise RuntimeError(state["message"])

        self._ensure_iproxy()
        if probe_wda("http://127.0.0.1:8100"):
            self.url = "http://127.0.0.1:8100"
            os.environ["WDA_URL"] = self.url
            self.ready = True
            self.message = f"WDA prêt sur {self.url}"
            return self.url

        udid = preferred_udid()
        if not udid:
            raise RuntimeError("aucun UDID iPhone")
        self._start_xcodebuild(udid)

        deadline = time.time() + timeout
        while time.time() < deadline:
            url = self._read_announced_url()
            if url and probe_wda(url):
                self.url = url
                os.environ["WDA_URL"] = url
                self.ready = True
                self.message = f"WDA prêt sur {url}"
                return url
            for candidate in _candidate_urls(self.url):
                if probe_wda(candidate):
                    self.url = candidate
                    os.environ["WDA_URL"] = candidate
                    self.ready = True
                    self.message = f"WDA prêt sur {candidate}"
                    return candidate
            if self._xcode and self._xcode.poll() is not None:
                raise RuntimeError(
                    "xcodebuild s'est arrêté avant que WDA réponde — "
                    "profil de provisionnement expiré ?"
                )
            time.sleep(2)
        raise RuntimeError(f"WDA n'a pas répondu en {int(timeout)}s")

    def _ensure_iproxy(self) -> None:
        if self._iproxy and self._iproxy.poll() is None:
            return
        if not shutil.which("iproxy"):
            return
        self._iproxy = subprocess.Popen(
            ["iproxy", "8100", "8100"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )

    def _start_xcodebuild(self, udid: str) -> None:
        if self._xcode and self._xcode.poll() is None:
            return
        cmd = build_xcodebuild_cmd(udid)
        self._xcode = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )

    def _read_announced_url(self) -> str | None:
        proc = self._xcode
        if proc is None or proc.stdout is None:
            return None
        found = None
        try:
            import select
            while True:
                ready, _, _ = select.select([proc.stdout], [], [], 0)
                if not ready:
                    break
                line = proc.stdout.readline()
                if not line:
                    break
                url = parse_server_url(line)
                if url:
                    found = url
        except (OSError, ValueError):
            return found
        return found

    def stop(self) -> None:
        for proc in (self._xcode, self._iproxy):
            if proc and proc.poll() is None:
                proc.terminate()


def _candidate_urls(current: str) -> list[str]:
    extras = [
        current,
        os.environ.get("WDA_URL", ""),
        "http://127.0.0.1:8100",
        "http://localhost:8100",
        "http://169.254.140.1:8100",
    ]
    seen: list[str] = []
    for url in extras:
        url = (url or "").rstrip("/")
        if url and url not in seen:
            seen.append(url)
    return seen
