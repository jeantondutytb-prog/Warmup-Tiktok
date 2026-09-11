#!/usr/bin/env python3
"""
Test the WORKING configuration: connect to WDA via WiFi IP (bypassing RemoteXPC).
This is how it worked this morning.
"""
import json, subprocess, tempfile, time, threading
from appium import webdriver
from appium.options.ios import XCUITestOptions

TEAM_ID = "U284BGAVKL"
WDA_BUNDLE_ID = "com.jean.wda.runner"

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
def timed_cmd(driver, name, func, timeout_s=15):
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
    options.new_command_timeout = 300
    options.auto_accept_alerts = True
    options.set_capability("xcodeOrgId", TEAM_ID)
    options.set_capability("xcodeSigningId", "Apple Development")
    options.set_capability("updatedWDABundleId", WDA_BUNDLE_ID)
    options.set_capability("usePreinstalledWDA", True)
    # THE KEY: connect to WDA via WiFi, bypassing RemoteXPC!
    options.set_capability("webDriverAgentUrl", "http://192.168.1.49:8100")
    options.set_capability("shouldWaitForQuiescence", False)
    options.set_capability("waitForIdleTimeout", 0)
    options.set_capability("simpleIsVisibleCheck", True)

    print("\n=== Creating session with TikTok via WiFi WDA ===")
    try:
        driver = webdriver.Remote(command_executor="http://localhost:4723", options=options)
    except Exception as e:
        print(f"Session FAILED: {e}")
        return
    print(f"Session: {driver.session_id}")

    print("\n--- Testing commands ---")
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

    total = sum([ok1, ok2, ok3, ok4, ok5, ok6])
    print(f"\n=== {total}/6 passed ===")
    if total >= 5:
        print("*** TikTok automation WORKING! ***")

    try:
        driver.quit()
    except:
        pass
    print("Done!")

if __name__ == "__main__":
    main()
