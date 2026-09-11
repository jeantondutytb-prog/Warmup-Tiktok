#!/usr/bin/env python3
"""
THE FIX: Create session with Settings, set snapshotMaxDepth=10,
then activate TikTok. The low snapshot depth prevents XCUITest
from freezing on TikTok's massive element tree.
"""
import json, subprocess, tempfile, time, threading
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
def timed_cmd(driver, name, func, timeout_s=20):
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
    options.bundle_id = "com.apple.Preferences"  # Start with Settings!
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

    print("\n1. Creating session with Settings...")
    driver = webdriver.Remote(command_executor="http://localhost:4723", options=options)
    print(f"   Session: {driver.session_id}")

    # Verify Settings works
    timed_cmd(driver, "baseline_size", lambda: driver.get_window_size())

    # Apply the fix BEFORE activating TikTok
    print("\n2. Setting snapshotMaxDepth=10 (THE FIX)...")
    driver.update_settings({
        "snapshotMaxDepth": 10,
        "customSnapshotTimeout": 5,
        "animationCoolOffTimeout": 0,
        "snapshotTimeout": 5,
    })
    print("   Settings applied!")

    # Verify settings took effect
    settings = driver.get_settings()
    print(f"   snapshotMaxDepth = {settings.get('snapshotMaxDepth')}")

    # Now activate TikTok
    print("\n3. Activating TikTok...")
    driver.activate_app("com.zhiliaoapp.musically")
    print("   TikTok activated!")
    time.sleep(3)

    # Test ALL the things
    print("\n=== Testing with TikTok in foreground ===")

    ok1 = timed_cmd(driver, "window_size", lambda: driver.get_window_size())
    ok2 = timed_cmd(driver, "screenshot", lambda: f"{len(driver.get_screenshot_as_base64())} chars")

    ok3 = timed_cmd(driver, "swipe_up", lambda: driver.execute_script(
        "mobile: swipe", {"direction": "up", "velocity": 1500}))
    time.sleep(1)

    ok4 = timed_cmd(driver, "tap_center", lambda: driver.execute_script(
        "mobile: tap", {"x": 187, "y": 406}))
    time.sleep(1)

    ok5 = timed_cmd(driver, "double_tap", lambda: driver.execute_script(
        "mobile: doubleTap", {"x": 187, "y": 406}))
    time.sleep(1)

    ok6 = timed_cmd(driver, "swipe_up_2", lambda: driver.execute_script(
        "mobile: swipe", {"direction": "up", "velocity": 1500}))

    total_ok = sum([ok1, ok2, ok3, ok4, ok5, ok6])
    print(f"\n=== Results: {total_ok}/6 passed ===")

    if total_ok == 6:
        print("\n*** ALL TESTS PASSED! TikTok automation is WORKING! ***")
    elif total_ok > 0:
        print("\n*** PARTIAL SUCCESS — some commands work ***")
    else:
        print("\n*** ALL FAILED — snapshotMaxDepth didn't fix it ***")

    print("\nCleaning up...")
    try:
        driver.quit()
    except:
        pass
    print("Done!")

if __name__ == "__main__":
    main()
