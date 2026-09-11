#!/usr/bin/env python3
"""Test: create session with Settings, then try system-level commands while TikTok is visible."""
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

    print("1. Session with Settings...")
    signal.signal(signal.SIGALRM, timeout_handler)
    driver = webdriver.Remote(command_executor="http://localhost:4723", options=options)
    signal.alarm(10)
    size = driver.get_window_size()
    signal.alarm(0)
    print(f"   OK: {size}")

    print("2. Activate TikTok...")
    signal.alarm(10)
    driver.activate_app("com.zhiliaoapp.musically")
    signal.alarm(0)
    print("   OK")
    time.sleep(3)

    # Test system-level command (doesn't touch TikTok's view)
    print("3. pressButton home (system level)...")
    signal.alarm(15)
    try:
        driver.execute_script("mobile: pressButton", {"name": "home"})
        signal.alarm(0)
        print("   OK!")
        time.sleep(2)
    except Exception as e:
        signal.alarm(0)
        print(f"   FAILED: {e}")

    # Try screenshot (WDA captures screen, doesn't query app view)
    print("4. screenshot...")
    signal.alarm(15)
    try:
        b64 = driver.get_screenshot_as_base64()
        signal.alarm(0)
        print(f"   OK: {len(b64)} bytes")
    except Exception as e:
        signal.alarm(0)
        print(f"   FAILED: {e}")

    # Try source (this queries the view)
    print("5. page_source (view query)...")
    signal.alarm(15)
    try:
        src = driver.page_source
        signal.alarm(0)
        print(f"   OK: {len(src)} chars")
    except Exception as e:
        signal.alarm(0)
        print(f"   FAILED: {e}")

    # Reactivate TikTok and try again
    print("6. Re-activate TikTok + pressButton...")
    signal.alarm(10)
    try:
        driver.activate_app("com.zhiliaoapp.musically")
        signal.alarm(0)
        print("   TikTok active")
    except Exception as e:
        signal.alarm(0)
        print(f"   FAILED: {e}")

    time.sleep(2)

    signal.alarm(15)
    try:
        driver.execute_script("mobile: pressButton", {"name": "volumeUp"})
        signal.alarm(0)
        print("   volumeUp OK!")
    except Exception as e:
        signal.alarm(0)
        print(f"   volumeUp FAILED: {e}")

    print("\nDone.")
    try:
        driver.quit()
    except:
        pass

if __name__ == "__main__":
    main()
