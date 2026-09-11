#!/usr/bin/env python3
"""
THE FIX: Use snapshotMaxDepth=10 to prevent XCUITest from freezing
when TikTok loads its massive element tree.
"""
import json, subprocess, tempfile, time, signal, sys, threading
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

result_box = {}

def timed_command(driver, name, func, timeout_s=15):
    def worker():
        try:
            result_box["r"] = func()
            result_box["e"] = None
        except Exception as e:
            result_box["r"] = None
            result_box["e"] = str(e)[:200]
    result_box.clear()
    t = threading.Thread(target=worker)
    start = time.time()
    t.start()
    t.join(timeout=timeout_s)
    elapsed = time.time() - start
    if t.is_alive():
        print(f"   {name}: TIMEOUT ({timeout_s}s)")
        return False
    elif result_box.get("e"):
        print(f"   {name}: ERROR ({elapsed:.1f}s) — {result_box['e']}")
        return False
    else:
        print(f"   {name}: OK ({elapsed:.1f}s) — {result_box.get('r')}")
        return True

def main():
    udid = get_udid()
    print(f"iPhone: {udid}")

    options = XCUITestOptions()
    options.platform_name = "iOS"
    options.udid = udid
    options.bundle_id = "com.zhiliaoapp.musically"
    options.no_reset = True
    options.new_command_timeout = 600
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
    options.set_capability("simpleIsVisibleCheck", True)
    # THE FIX: limit snapshot depth to prevent TikTok's massive element tree from freezing XCUITest
    options.set_capability("appium:settings[snapshotMaxDepth]", 10)
    options.set_capability("appium:settings[customSnapshotTimeout]", 5)
    options.set_capability("appium:settings[animationCoolOffTimeout]", 0)

    print("\n=== Creating session DIRECTLY with TikTok (snapshotMaxDepth=10) ===")
    print("(This previously hung indefinitely...)")

    try:
        driver = webdriver.Remote(command_executor="http://localhost:4723", options=options)
    except Exception as e:
        print(f"Session creation FAILED: {e}")
        return

    print(f"Session created: {driver.session_id}")

    # Test 1: window size
    print("\n--- Testing commands ---")
    timed_command(driver, "window_size", lambda: driver.get_window_size())

    # Test 2: screenshot
    timed_command(driver, "screenshot", lambda: f"{len(driver.get_screenshot_as_base64())} chars")

    # Test 3: swipe
    timed_command(driver, "swipe_up", lambda: driver.execute_script("mobile: swipe", {"direction": "up", "velocity": 1500}))

    time.sleep(1)

    # Test 4: tap
    timed_command(driver, "tap_center", lambda: driver.execute_script("mobile: tap", {"x": 187, "y": 406}))

    time.sleep(1)

    # Test 5: double tap (like)
    timed_command(driver, "double_tap", lambda: driver.execute_script("mobile: doubleTap", {"x": 187, "y": 406}))

    time.sleep(1)

    # Test 6: another swipe
    timed_command(driver, "swipe_up_2", lambda: driver.execute_script("mobile: swipe", {"direction": "up", "velocity": 1500}))

    time.sleep(2)

    # Test 7: screenshot after interactions
    timed_command(driver, "screenshot_2", lambda: f"{len(driver.get_screenshot_as_base64())} chars")

    print("\n=== ALL TESTS COMPLETE ===")
    try:
        driver.quit()
    except:
        pass
    print("Done!")

if __name__ == "__main__":
    main()
