#!/usr/bin/env python3
"""Clean test: Settings only, verify WDA works, then try TikTok. Properly quit between tests."""
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

def make_options(udid, bundle_id):
    options = XCUITestOptions()
    options.platform_name = "iOS"
    options.udid = udid
    options.bundle_id = bundle_id
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
    return options

def timeout_handler(signum, frame):
    raise TimeoutError("TIMEOUT")

def main():
    udid = get_udid()
    print(f"iPhone: {udid}")
    signal.signal(signal.SIGALRM, timeout_handler)

    # === TEST 1: Settings ===
    print("\n=== TEST 1: Settings ===")
    options = make_options(udid, "com.apple.Preferences")
    driver = webdriver.Remote(command_executor="http://localhost:4723", options=options)
    print("Session OK")

    signal.alarm(15)
    try:
        size = driver.get_window_size()
        signal.alarm(0)
        print(f"get_window_size: {size}")
    except TimeoutError:
        signal.alarm(0)
        print("get_window_size: TIMEOUT")
        print("WDA is broken. Quitting.")
        try: driver.quit()
        except: pass
        return

    signal.alarm(15)
    try:
        driver.execute_script("mobile: swipe", {"direction": "down", "velocity": 1000})
        signal.alarm(0)
        print("swipe: OK")
    except TimeoutError:
        signal.alarm(0)
        print("swipe: TIMEOUT")
    except Exception as e:
        signal.alarm(0)
        print(f"swipe: {e}")

    # PROPERLY QUIT
    print("Quitting Settings session...")
    driver.quit()
    time.sleep(3)

    # === TEST 2: TikTok ===
    print("\n=== TEST 2: TikTok ===")
    options = make_options(udid, "com.zhiliaoapp.musically")
    options.set_capability("forceAppLaunch", True)
    options.set_capability("shouldTerminateApp", True)
    driver = webdriver.Remote(command_executor="http://localhost:4723", options=options)
    print("Session OK")

    signal.alarm(20)
    try:
        size = driver.get_window_size()
        signal.alarm(0)
        print(f"get_window_size: {size}")
    except TimeoutError:
        signal.alarm(0)
        print("get_window_size: TIMEOUT (expected)")

    signal.alarm(20)
    try:
        driver.execute_script("mobile: swipe", {"direction": "up", "velocity": 1500})
        signal.alarm(0)
        print("swipe: OK!!!!")
    except TimeoutError:
        signal.alarm(0)
        print("swipe: TIMEOUT")
    except Exception as e:
        signal.alarm(0)
        print(f"swipe: {e}")

    signal.alarm(20)
    try:
        b64 = driver.get_screenshot_as_base64()
        signal.alarm(0)
        print(f"screenshot: OK ({len(b64)} bytes)")
    except TimeoutError:
        signal.alarm(0)
        print("screenshot: TIMEOUT")
    except Exception as e:
        signal.alarm(0)
        print(f"screenshot: {e}")

    print("Quitting TikTok session...")
    try: driver.quit()
    except: pass

    print("\nDone.")

if __name__ == "__main__":
    main()
