#!/usr/bin/env python3
"""
DEFINITIVE FIX: WiFi WDA + snapshotMaxDepth + Settings-first approach.
Combines everything that works:
1. Connect to pre-existing WDA via WiFi (bypass RemoteXPC)
2. usePreinstalledWDA=True (don't let Appium kill WDA)  
3. Start with Settings, set snapshotMaxDepth=10, then activate TikTok
"""
import time, threading
from appium import webdriver
from appium.options.ios import XCUITestOptions

UDID = "00008020-000D0CE43A99002E"
TEAM_ID = "U284BGAVKL"
WDA_BUNDLE_ID = "com.jean.wda.runner"

def timed_cmd(driver, name, func, timeout_s=15):
    result = {}
    def worker():
        try:
            result["r"] = func()
        except Exception as e:
            result["e"] = str(e)[:200]
    t = threading.Thread(target=worker)
    start = time.time()
    t.start()
    t.join(timeout=timeout_s)
    elapsed = time.time() - start
    if t.is_alive():
        print(f"   {name}: TIMEOUT ({timeout_s}s)")
        return False
    elif "e" in result:
        print(f"   {name}: ERROR ({elapsed:.1f}s) - {result['e']}")
        return False
    else:
        r = result.get("r")
        display = str(r)[:100] if r is not None else "None"
        print(f"   {name}: OK ({elapsed:.1f}s) - {display}")
        return True

def main():
    options = XCUITestOptions()
    options.platform_name = "iOS"
    options.udid = UDID
    options.bundle_id = "com.apple.Preferences"  # Start with Settings
    options.no_reset = True
    options.new_command_timeout = 300
    options.auto_accept_alerts = True
    options.set_capability("xcodeOrgId", TEAM_ID)
    options.set_capability("xcodeSigningId", "Apple Development")
    options.set_capability("updatedWDABundleId", WDA_BUNDLE_ID)
    # KEY: connect to existing WDA via WiFi, don't let Appium manage WDA
    options.set_capability("usePreinstalledWDA", True)
    options.set_capability("webDriverAgentUrl", "http://192.168.1.49:8100")
    options.set_capability("shouldWaitForQuiescence", False)
    options.set_capability("waitForIdleTimeout", 0)
    options.set_capability("simpleIsVisibleCheck", True)

    print("1. Creating session with Settings via WiFi WDA...")
    try:
        driver = webdriver.Remote(command_executor="http://localhost:4723", options=options)
    except Exception as e:
        print(f"   FAILED: {e}")
        return
    print(f"   Session: {driver.session_id}")

    # Verify baseline works
    timed_cmd(driver, "baseline_size", lambda: driver.get_window_size())

    # Apply snapshotMaxDepth BEFORE TikTok
    print("\n2. Setting snapshotMaxDepth=10...")
    driver.update_settings({
        "snapshotMaxDepth": 10,
        "customSnapshotTimeout": 5,
        "animationCoolOffTimeout": 0,
        "snapshotTimeout": 5,
    })
    s = driver.get_settings()
    print(f"   snapshotMaxDepth = {s.get('snapshotMaxDepth')}")

    # Activate TikTok
    print("\n3. Activating TikTok...")
    driver.activate_app("com.zhiliaoapp.musically")
    print("   TikTok activated!")
    time.sleep(3)

    # Test everything
    print("\n=== Testing with TikTok ===")
    ok1 = timed_cmd(driver, "window_size", lambda: driver.get_window_size())
    ok2 = timed_cmd(driver, "screenshot", lambda: f"{len(driver.get_screenshot_as_base64())} chars")

    ok3 = timed_cmd(driver, "swipe_up_1", lambda: driver.execute_script(
        "mobile: swipe", {"direction": "up", "velocity": 1500}))
    time.sleep(2)

    ok4 = timed_cmd(driver, "tap_center", lambda: driver.execute_script(
        "mobile: tap", {"x": 187, "y": 406}))
    time.sleep(1)

    ok5 = timed_cmd(driver, "double_tap", lambda: driver.execute_script(
        "mobile: doubleTap", {"x": 187, "y": 406}))
    time.sleep(1)

    ok6 = timed_cmd(driver, "swipe_up_2", lambda: driver.execute_script(
        "mobile: swipe", {"direction": "up", "velocity": 1500}))

    total = sum([ok1, ok2, ok3, ok4, ok5, ok6])
    print(f"\n=== {total}/6 passed ===")
    if total >= 5:
        print("*** TikTok automation WORKING! ***")
    elif total > 0:
        print("*** PARTIAL - some commands work ***")
    else:
        print("*** ALL FAILED ***")

    try:
        driver.quit()
    except:
        pass
    print("Done!")

if __name__ == "__main__":
    main()
