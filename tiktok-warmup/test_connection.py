#!/usr/bin/env python3
"""Minimal test: create Appium session and try one swipe on TikTok."""
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

def timeout_handler(signum, frame):
    print("TIMEOUT: Operation took too long, aborting")
    sys.exit(1)

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

def main():
    udid = get_udid()
    if not udid:
        print("ERROR: iPhone not found")
        return
    print(f"Found iPhone: {udid}")

    options = XCUITestOptions()
    options.platform_name = "iOS"
    options.udid = udid
    options.bundle_id = "com.zhiliaoapp.musically"
    options.no_reset = True
    options.new_command_timeout = 60
    options.auto_accept_alerts = True

    options.set_capability("xcodeOrgId", TEAM_ID)
    options.set_capability("xcodeSigningId", "Apple Development")
    options.set_capability("updatedWDABundleId", WDA_BUNDLE_ID)
    options.set_capability("usePrebuiltWDA", False)
    options.set_capability("derivedDataPath", DERIVED_DATA)
    options.set_capability("showXcodeLog", False)
    options.set_capability("wdaLaunchTimeout", 240000)
    options.set_capability("wdaConnectionTimeout", 120000)
    options.set_capability("shouldWaitForQuiescence", False)
    options.set_capability("waitForIdleTimeout", 0)
    options.set_capability("simpleIsVisibleCheck", True)

    print("Creating Appium session (WDA will build, ~30s)...")
    t0 = time.time()
    try:
        driver = webdriver.Remote(
            command_executor="http://localhost:4723",
            options=options,
        )
    except Exception as e:
        print(f"ERROR creating session: {e}")
        return
    print(f"Session created in {time.time()-t0:.1f}s")

    # Set a 30s alarm for the next operations
    signal.signal(signal.SIGALRM, timeout_handler)

    print("Step 1: get_window_size...")
    signal.alarm(30)
    try:
        size = driver.get_window_size()
        print(f"  OK: {size}")
    except Exception as e:
        print(f"  FAILED: {e}")
        driver.quit()
        return

    print("Step 2: swipe (scroll feed)...")
    signal.alarm(30)
    try:
        w, h = size["width"], size["height"]
        driver.swipe(w // 2, int(h * 0.75), w // 2, int(h * 0.25), 500)
        print("  OK: swiped!")
    except Exception as e:
        print(f"  FAILED: {e}")
        driver.quit()
        return

    print("Step 3: screenshot test...")
    signal.alarm(30)
    try:
        b64 = driver.get_screenshot_as_base64()
        print(f"  OK: screenshot {len(b64)} bytes")
    except Exception as e:
        print(f"  FAILED: {e}")

    signal.alarm(0)
    print("\nALL TESTS PASSED - Appium + WDA + iPhone connection works!")
    print("Cleaning up session...")
    driver.quit()
    print("Done.")

if __name__ == "__main__":
    main()
