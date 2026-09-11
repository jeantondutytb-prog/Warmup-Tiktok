#!/usr/bin/env python3
"""Session without bundleId - just send raw touch events to screen."""
import json, subprocess, tempfile, time, signal, sys
from appium import webdriver
from appium.options.ios import XCUITestOptions

TEAM_ID = "U284BGAVKL"
WDA_BUNDLE_ID = "com.jean.wda.runner"
DERIVED_DATA = "/Users/jean/Library/Developer/Xcode/DerivedData/WebDriverAgent-entqkdybqjzegiahlgkxvxghpzdf"

def get_udid():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        tmp_path = f.name
    subprocess.run(["xcrun", "devicectl", "list", "devices", "--json-output", tmp_path],
                   capture_output=True, text=True)
    with open(tmp_path) as f:
        data = json.load(f)
    for d in data.get("result", {}).get("devices", []):
        hw, conn, props = d.get("hardwareProperties", {}), d.get("connectionProperties", {}), d.get("deviceProperties", {})
        if hw.get("deviceType") == "iPhone" and conn.get("pairingState") == "paired" and props.get("bootState") == "booted":
            return hw.get("udid")

def timeout_handler(signum, frame):
    print("TIMEOUT")
    sys.exit(1)

def main():
    udid = get_udid()
    print(f"iPhone: {udid}")

    options = XCUITestOptions()
    options.platform_name = "iOS"
    options.udid = udid
    # NO bundleId - don't target any app
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

    print("1. Creating session (no bundleId)...")
    signal.signal(signal.SIGALRM, timeout_handler)
    try:
        driver = webdriver.Remote(command_executor="http://localhost:4723", options=options)
    except Exception as e:
        print(f"FAILED: {e}")
        return
    print("   OK")

    print("2. get_window_size...")
    signal.alarm(15)
    try:
        size = driver.get_window_size()
        signal.alarm(0)
        print(f"   OK: {size}")
    except Exception as e:
        signal.alarm(0)
        print(f"   FAILED: {e}")

    # TikTok should already be in foreground from last test
    print("3. mobile:swipe up...")
    signal.alarm(15)
    try:
        driver.execute_script("mobile: swipe", {"direction": "up", "velocity": 1500})
        signal.alarm(0)
        print("   OK: SWIPED!")
    except Exception as e:
        signal.alarm(0)
        print(f"   FAILED: {e}")

    time.sleep(1)

    print("4. mobile:doubleTap (like)...")
    signal.alarm(15)
    try:
        driver.execute_script("mobile: doubleTap", {"x": 187, "y": 406})
        signal.alarm(0)
        print("   OK: DOUBLE-TAPPED!")
    except Exception as e:
        signal.alarm(0)
        print(f"   FAILED: {e}")

    print("5. screenshot...")
    signal.alarm(15)
    try:
        b64 = driver.get_screenshot_as_base64()
        signal.alarm(0)
        print(f"   OK: {len(b64)} bytes")
    except Exception as e:
        signal.alarm(0)
        print(f"   FAILED: {e}")

    print("\nDone.")
    try:
        driver.quit()
    except:
        pass

if __name__ == "__main__":
    main()
