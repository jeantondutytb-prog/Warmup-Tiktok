#!/usr/bin/env python3
"""
Precise timing test: activate TikTok then immediately send commands.
Test if there's a window where commands work before RemoteXPC breaks.
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

result_holder = {"result": None, "error": None}

def timed_command(driver, name, func, timeout_s=10):
    """Run a command with a timeout using threads."""
    def worker():
        try:
            result_holder["result"] = func()
            result_holder["error"] = None
        except Exception as e:
            result_holder["result"] = None
            result_holder["error"] = str(e)

    result_holder["result"] = None
    result_holder["error"] = None
    t = threading.Thread(target=worker)
    start = time.time()
    t.start()
    t.join(timeout=timeout_s)
    elapsed = time.time() - start

    if t.is_alive():
        print(f"   {name}: TIMEOUT ({timeout_s}s, elapsed {elapsed:.1f}s)")
        return False
    elif result_holder["error"]:
        print(f"   {name}: ERROR ({elapsed:.1f}s) — {result_holder['error'][:100]}")
        return False
    else:
        print(f"   {name}: OK ({elapsed:.1f}s) — {result_holder['result']}")
        return True

def main():
    udid = get_udid()
    print(f"iPhone: {udid}")

    options = XCUITestOptions()
    options.platform_name = "iOS"
    options.udid = udid
    options.bundle_id = "com.apple.Preferences"
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

    print("\n=== Phase 1: Settings (baseline) ===")
    driver = webdriver.Remote(command_executor="http://localhost:4723", options=options)
    print(f"Session: {driver.session_id}")

    timed_command(driver, "window_size", lambda: driver.get_window_size())
    timed_command(driver, "pressButton_home", lambda: driver.execute_script("mobile: pressButton", {"name": "home"}))
    timed_command(driver, "screenshot", lambda: f"{len(driver.get_screenshot_as_base64())} chars")
    timed_command(driver, "swipe_settings", lambda: driver.execute_script("mobile: swipe", {"direction": "up", "velocity": 1000}))

    print("\n=== Phase 2: Activate TikTok ===")
    driver.activate_app("com.zhiliaoapp.musically")
    print("TikTok activated!")

    # NO SLEEP — test immediately
    print("\nTesting immediately (0s delay):")
    ok = timed_command(driver, "pressButton_home_0s", lambda: driver.execute_script("mobile: pressButton", {"name": "home"}), timeout_s=8)

    if ok:
        print("\n--- pressButton worked at 0s! Trying with TikTok again ---")
        time.sleep(1)
        driver.activate_app("com.zhiliaoapp.musically")
        time.sleep(0.5)
        timed_command(driver, "swipe_0.5s", lambda: driver.execute_script("mobile: swipe", {"direction": "up", "velocity": 1500}), timeout_s=8)

        # Try again
        driver.activate_app("com.zhiliaoapp.musically")
        time.sleep(0.5)
        timed_command(driver, "tap_0.5s", lambda: driver.execute_script("mobile: tap", {"x": 187, "y": 406}), timeout_s=8)

        # Screenshot while on tiktok
        driver.activate_app("com.zhiliaoapp.musically")
        time.sleep(1)
        timed_command(driver, "screenshot_tiktok", lambda: f"{len(driver.get_screenshot_as_base64())} chars", timeout_s=8)
    else:
        # pressButton failed at 0s too
        print("\n--- pressButton also hangs. WDA connection broken. ---")

        # Try to reconnect by going back to Settings
        print("\n=== Phase 3: Recovery attempt ===")
        # Can we terminate and go to settings?
        timed_command(driver, "terminate_tiktok", lambda: driver.terminate_app("com.zhiliaoapp.musically"), timeout_s=8)
        time.sleep(1)
        timed_command(driver, "activate_settings", lambda: driver.activate_app("com.apple.Preferences"), timeout_s=8)
        time.sleep(1)
        timed_command(driver, "swipe_after_recovery", lambda: driver.execute_script("mobile: swipe", {"direction": "up", "velocity": 1000}), timeout_s=8)

    print("\nCleaning up...")
    try:
        driver.quit()
    except:
        pass
    print("Done!")

if __name__ == "__main__":
    main()
