#!/usr/bin/env python3
"""Kill TikTok, relaunch it, then test commands."""
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
    signal.signal(signal.SIGALRM, timeout_handler)
    driver = webdriver.Remote(command_executor="http://localhost:4723", options=options)
    print("   OK")

    signal.alarm(10)
    size = driver.get_window_size()
    signal.alarm(0)
    print(f"2. Window size: {size}")

    print("3. Killing TikTok...")
    signal.alarm(10)
    try:
        driver.terminate_app("com.zhiliaoapp.musically")
        signal.alarm(0)
        print("   OK: TikTok terminated")
    except Exception as e:
        signal.alarm(0)
        print(f"   Note: {e}")

    time.sleep(2)

    print("4. Relaunching TikTok...")
    signal.alarm(15)
    try:
        driver.activate_app("com.zhiliaoapp.musically")
        signal.alarm(0)
        print("   OK: TikTok launched")
    except Exception as e:
        signal.alarm(0)
        print(f"   FAILED: {e}")
        driver.quit()
        return

    time.sleep(3)

    print("5. Trying mobile:swipe on fresh TikTok...")
    signal.alarm(20)
    try:
        driver.execute_script("mobile: swipe", {"direction": "up", "velocity": 1500})
        signal.alarm(0)
        print("   OK: SWIPED!")
    except Exception as e:
        signal.alarm(0)
        print(f"   FAILED: {e}")

    time.sleep(1)

    print("6. Trying mobile:tap...")
    signal.alarm(20)
    try:
        driver.execute_script("mobile: tap", {"x": 187, "y": 400})
        signal.alarm(0)
        print("   OK: TAPPED!")
    except Exception as e:
        signal.alarm(0)
        print(f"   FAILED: {e}")

    print("7. Trying screenshot...")
    signal.alarm(20)
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
