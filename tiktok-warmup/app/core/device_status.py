"""État iPhone + WebDriverAgent pour l'écran de lancement rapide."""

from __future__ import annotations

import json
import os
import subprocess
import tempfile
import urllib.error
import urllib.request

from app.core.appium_driver import AppiumDriverManager


def _wda_ready(wda_url: str, timeout: float = 3.0) -> tuple[bool, str]:
    try:
        req = urllib.request.Request(f"{wda_url.rstrip('/')}/status")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read())
        if data.get("value", {}).get("ready"):
            return True, "WebDriverAgent prêt"
        return False, "WebDriverAgent répond mais n'est pas prêt"
    except urllib.error.URLError:
        return False, "WebDriverAgent inaccessible — lance xcodebuild ou vérifie WDA_URL"
    except TimeoutError:
        return False, "WebDriverAgent ne répond pas (timeout)"
    except OSError:
        return False, "WebDriverAgent inaccessible"


def _detect_iphone() -> dict:
    """Détecte un iPhone branché via devicectl (macOS) ou idevice_id."""
    via_devicectl = _iphone_via_devicectl()
    if via_devicectl["connected"]:
        return via_devicectl
    return _iphone_via_idevice_id()


def _iphone_via_devicectl() -> dict:
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        tmp_path = f.name
    try:
        proc = subprocess.run(
            ["xcrun", "devicectl", "list", "devices", "--json-output", tmp_path],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if proc.returncode != 0:
            return {"connected": False, "udid": None, "name": None, "message": "devicectl indisponible"}
        with open(tmp_path) as f:
            data = json.load(f)
    except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError, OSError):
        return {"connected": False, "udid": None, "name": None, "message": "devicectl indisponible"}
    finally:
        try:
            os.unlink(tmp_path)
        except OSError:
            pass

    for device in data.get("result", {}).get("devices", []):
        hw = device.get("hardwareProperties", {})
        conn = device.get("connectionProperties", {})
        props = device.get("deviceProperties", {})
        if (
            hw.get("deviceType") == "iPhone"
            and conn.get("pairingState") == "paired"
            and props.get("bootState") == "booted"
        ):
            name = props.get("name") or "iPhone"
            udid = hw.get("udid")
            return {
                "connected": True,
                "udid": udid,
                "name": name,
                "message": f"{name} connecté",
            }
    return {"connected": False, "udid": None, "name": None, "message": "Aucun iPhone détecté — branche-le en USB"}


def _iphone_via_idevice_id() -> dict:
    try:
        proc = subprocess.run(
            ["idevice_id", "-l"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        udids = [u.strip() for u in proc.stdout.strip().split("\n") if u.strip()]
        if udids:
            return {
                "connected": True,
                "udid": udids[0],
                "name": "iPhone",
                "message": "iPhone connecté (USB)",
            }
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass
    return {"connected": False, "udid": None, "name": None, "message": "Aucun iPhone détecté — branche-le en USB"}


def get_device_status(wda_url: str | None = None) -> dict:
    url = wda_url or os.environ.get("WDA_URL", "http://169.254.140.1:8100")
    iphone = _detect_iphone()
    wda_ready, wda_message = _wda_ready(url)
    return {
        "iphone": iphone,
        "wda": {"ready": wda_ready, "url": url, "message": wda_message},
        "ready": iphone["connected"] and wda_ready,
    }
