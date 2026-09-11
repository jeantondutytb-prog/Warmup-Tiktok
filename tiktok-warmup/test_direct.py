#!/usr/bin/env python3
"""Direct TikTok session + immediate swipe, no get_window_size."""
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
    options.bundle_id = "com.zhiliaoapp.musically"
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

    print("Creating TikTok session...")
    signal.signal(signal.SIGALRM, timeout_handler)
    try:
        driver = webdriver.Remote(command_executor="http://localhost:4723", options=options)
    except Exception as e:
        print(f"FAILED: {e}")
        return
    print("Session OK")

    # Try W3C Actions directly (touch action pointer)
    print("Test A: W3C Actions pointer swipe...")
    signal.alarm(15)
    try:
        from selenium.webdriver.common.action_chains import ActionChains
        from selenium.webdriver.common.actions.pointer_input import PointerInput
        from selenium.webdriver.common.actions import interaction

        pointer = PointerInput(interaction.POINTER_TOUCH, "finger")
        actions = ActionChains(driver)
        actions.w3c_actions.devices = []
        actions.w3c_actions.add_pointer_input("touch", "finger")
        finger = actions.w3c_actions.devices[0]
        finger.create_pointer_move(x=187, y=600, duration=0)
        finger.create_pointer_down(button=0)
        finger.create_pointer_move(x=187, y=200, duration=500)
        finger.create_pointer_up(button=0)
        actions.perform()
        signal.alarm(0)
        print("  OK!")
    except Exception as e:
        signal.alarm(0)
        print(f"  FAILED: {e}")

    time.sleep(1)

    # Try mobile: performTouch
    print("Test B: mobile: scroll...")
    signal.alarm(15)
    try:
        driver.execute_script("mobile: scroll", {"direction": "up"})
        signal.alarm(0)
        print("  OK!")
    except Exception as e:
        signal.alarm(0)
        print(f"  FAILED: {e}")

    time.sleep(1)

    # Try tap via coordinates
    print("Test C: mobile: tap center...")
    signal.alarm(15)
    try:
        driver.execute_script("mobile: tap", {"x": 187, "y": 400})
        signal.alarm(0)
        print("  OK!")
    except Exception as e:
        signal.alarm(0)
        print(f"  FAILED: {e}")

    # Try screenshot
    print("Test D: screenshot...")
    signal.alarm(15)
    try:
        b64 = driver.get_screenshot_as_base64()
        signal.alarm(0)
        print(f"  OK: {len(b64)} bytes")
    except Exception as e:
        signal.alarm(0)
        print(f"  FAILED: {e}")

    print("\nDone")
    try:
        driver.quit()
    except:
        pass

if __name__ == "__main__":
    main()
