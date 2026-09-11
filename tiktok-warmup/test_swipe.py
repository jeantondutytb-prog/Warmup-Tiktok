#!/usr/bin/env python3
"""Connect via Settings, activate TikTok, try direct swipe without querying UI."""
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
    print("TIMEOUT after 20s")
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
    options.set_capability("wdaLaunchTimeout", 240000)
    options.set_capability("wdaConnectionTimeout", 120000)
    options.set_capability("shouldWaitForQuiescence", False)
    options.set_capability("waitForIdleTimeout", 0)

    print("1. Creating session with Settings...")
    driver = webdriver.Remote(command_executor="http://localhost:4723", options=options)
    print("   OK")

    signal.signal(signal.SIGALRM, timeout_handler)

    # Verify WDA works
    signal.alarm(10)
    size = driver.get_window_size()
    signal.alarm(0)
    print(f"2. Window size: {size}")

    # Activate TikTok
    print("3. Activating TikTok...")
    signal.alarm(10)
    driver.activate_app("com.zhiliaoapp.musically")
    signal.alarm(0)
    print("   OK")
    time.sleep(2)

    # iPhone XS = 375x812 points
    W, H = 375, 812

    # Try mobile:swipe directly (WDA native, no UI query needed)
    print("4. Trying mobile:swipe...")
    signal.alarm(20)
    try:
        driver.execute_script("mobile: swipe", {
            "direction": "up",
            "velocity": 1500
        })
        signal.alarm(0)
        print("   OK: swiped up!")
        time.sleep(1)
    except Exception as e:
        signal.alarm(0)
        print(f"   FAILED: {e}")

    # Try mobile:tap
    print("5. Trying mobile:tap...")
    signal.alarm(20)
    try:
        driver.execute_script("mobile: tap", {
            "x": W // 2,
            "y": H // 2
        })
        signal.alarm(0)
        print("   OK: tapped!")
    except Exception as e:
        signal.alarm(0)
        print(f"   FAILED: {e}")

    # Try another swipe
    print("6. Trying another mobile:swipe...")
    signal.alarm(20)
    try:
        driver.execute_script("mobile: swipe", {
            "direction": "up",
            "velocity": 1500
        })
        signal.alarm(0)
        print("   OK: swiped again!")
    except Exception as e:
        signal.alarm(0)
        print(f"   FAILED: {e}")

    # Try mobile:doubleTap (like)
    print("7. Trying mobile:doubleTap...")
    signal.alarm(20)
    try:
        driver.execute_script("mobile: doubleTap", {
            "x": W // 2,
            "y": H // 2
        })
        signal.alarm(0)
        print("   OK: double-tapped!")
    except Exception as e:
        signal.alarm(0)
        print(f"   FAILED: {e}")

    # Try screenshot
    print("8. Trying screenshot...")
    signal.alarm(20)
    try:
        b64 = driver.get_screenshot_as_base64()
        signal.alarm(0)
        print(f"   OK: {len(b64)} bytes")
    except Exception as e:
        signal.alarm(0)
        print(f"   FAILED: {e}")

    print("\nALL DONE!")
    try:
        driver.quit()
    except Exception:
        pass

if __name__ == "__main__":
    main()
