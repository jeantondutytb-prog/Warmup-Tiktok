#!/usr/bin/env python3
"""Test WDA with Settings app (not TikTok) to isolate the issue."""
import json
import subprocess
import tempfile
import time
import signal
import sys

from appium import webdriver
from appium.options.ios import XCUITestOptions

TEAM_ID = "U284BGAVKL"
WDA_BUNDLE_ID = "com.jean.wda.runner"
DERIVED_DATA = "/Users/jean/Library/Developer/Xcode/DerivedData/WebDriverAgent-entqkdybqjzegiahlgkxvxghpzdf"

def get_udid():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        tmp_path = f.name
    subprocess.run(
        ["xcrun", "devicectl", "list", "devices", "--json-output", tmp_path],
        capture_output=True, text=True,
    )
    with open(tmp_path) as f:
        data = json.load(f)
    for device in data.get("result", {}).get("devices", []):
        hw = device.get("hardwareProperties", {})
        conn = device.get("connectionProperties", {})
        props = device.get("deviceProperties", {})
        if (hw.get("deviceType") == "iPhone"
            and conn.get("pairingState") == "paired"
            and props.get("bootState") == "booted"):
            return hw.get("udid")
    return None

def timeout_handler(signum, frame):
    print("TIMEOUT after 30s")
    sys.exit(1)

def main():
    udid = get_udid()
    print(f"iPhone: {udid}")

    options = XCUITestOptions()
    options.platform_name = "iOS"
    options.udid = udid
    options.bundle_id = "com.apple.Preferences"
    options.no_reset = True
    options.new_command_timeout = 60
    options.auto_accept_alerts = True

    options.set_capability("xcodeOrgId", TEAM_ID)
    options.set_capability("xcodeSigningId", "Apple Development")
    options.set_capability("updatedWDABundleId", WDA_BUNDLE_ID)
    options.set_capability("usePrebuiltWDA", True)
    options.set_capability("derivedDataPath", DERIVED_DATA)
    options.set_capability("showXcodeLog", False)
    options.set_capability("wdaLaunchTimeout", 240000)
    options.set_capability("wdaConnectionTimeout", 120000)
    options.set_capability("shouldWaitForQuiescence", False)
    options.set_capability("waitForIdleTimeout", 0)

    print("Creating session with Settings app...")
    t0 = time.time()
    try:
        driver = webdriver.Remote(command_executor="http://localhost:4723", options=options)
    except Exception as e:
        print(f"Session creation failed: {e}")
        return
    print(f"Session OK in {time.time()-t0:.1f}s")

    signal.signal(signal.SIGALRM, timeout_handler)
    signal.alarm(30)

    print("get_window_size...")
    try:
        size = driver.get_window_size()
        print(f"  OK: {size}")
    except Exception as e:
        print(f"  FAILED: {e}")
        driver.quit()
        return

    signal.alarm(0)
    print("SUCCESS - WDA works with Settings!")
    driver.quit()

if __name__ == "__main__":
    main()
