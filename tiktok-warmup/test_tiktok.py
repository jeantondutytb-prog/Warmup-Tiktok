#!/usr/bin/env python3
"""Connect via Settings, then switch to TikTok and test commands."""
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

    # Step 1: Connect via Settings (proven to work)
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
    options.set_capability("wdaLaunchTimeout", 240000)
    options.set_capability("wdaConnectionTimeout", 120000)
    options.set_capability("shouldWaitForQuiescence", False)
    options.set_capability("waitForIdleTimeout", 0)

    print("1. Creating session with Settings...")
    driver = webdriver.Remote(command_executor="http://localhost:4723", options=options)
    print(f"   Session OK")

    signal.signal(signal.SIGALRM, timeout_handler)

    print("2. get_window_size on Settings...")
    signal.alarm(15)
    size = driver.get_window_size()
    signal.alarm(0)
    print(f"   OK: {size}")

    print("3. Activating TikTok...")
    signal.alarm(15)
    try:
        driver.activate_app("com.zhiliaoapp.musically")
        signal.alarm(0)
        print("   OK: TikTok activated")
    except Exception as e:
        signal.alarm(0)
        print(f"   FAILED: {e}")
        driver.quit()
        return

    time.sleep(2)

    print("4. get_window_size on TikTok...")
    signal.alarm(15)
    try:
        size = driver.get_window_size()
        signal.alarm(0)
        print(f"   OK: {size}")
    except Exception as e:
        signal.alarm(0)
        print(f"   FAILED: {e}")
        print("   Trying to swipe anyway...")

    print("5. Trying swipe...")
    signal.alarm(15)
    try:
        driver.swipe(187, 600, 187, 200, 500)
        signal.alarm(0)
        print("   OK: swiped!")
    except Exception as e:
        signal.alarm(0)
        print(f"   FAILED: {e}")

    print("6. Trying screenshot...")
    signal.alarm(15)
    try:
        b64 = driver.get_screenshot_as_base64()
        signal.alarm(0)
        print(f"   OK: {len(b64)} bytes")
    except Exception as e:
        signal.alarm(0)
        print(f"   FAILED: {e}")

    print("\nDone. Cleaning up...")
    try:
        driver.quit()
    except Exception:
        pass

if __name__ == "__main__":
    main()
