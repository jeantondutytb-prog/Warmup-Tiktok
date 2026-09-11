#!/usr/bin/env python3
"""Test: Session with Settings, activate TikTok, then try touch commands WITHOUT view queries."""
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
    raise TimeoutError("TIMEOUT")

def main():
    udid = get_udid()
    print(f"iPhone: {udid}")
    signal.signal(signal.SIGALRM, timeout_handler)

    # Create session with Settings (proven to work)
    options = XCUITestOptions()
    options.platform_name = "iOS"
    options.udid = udid
    options.bundle_id = "com.apple.Preferences"
    options.no_reset = True
    options.new_command_timeout = 300
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

    print("1. Creating session with Settings...")
    driver = webdriver.Remote(command_executor="http://localhost:4723", options=options)
    signal.alarm(10)
    size = driver.get_window_size()
    signal.alarm(0)
    print(f"   Window: {size}")

    # Activate TikTok
    print("2. Activating TikTok...")
    signal.alarm(10)
    driver.activate_app("com.zhiliaoapp.musically")
    signal.alarm(0)
    print("   TikTok activated!")
    time.sleep(3)  # Let TikTok fully load

    # Try touch commands — these should NOT need view hierarchy
    print("3. mobile:tap at screen center (187, 406)...")
    signal.alarm(20)
    try:
        driver.execute_script("mobile: tap", {"x": 187, "y": 406})
        signal.alarm(0)
        print("   TAP OK!")
    except TimeoutError:
        signal.alarm(0)
        print("   TAP TIMEOUT")
    except Exception as e:
        signal.alarm(0)
        print(f"   TAP ERROR: {e}")

    time.sleep(1)

    print("4. mobile:swipe up (scroll feed)...")
    signal.alarm(20)
    try:
        driver.execute_script("mobile: swipe", {"direction": "up", "velocity": 1500})
        signal.alarm(0)
        print("   SWIPE OK!")
    except TimeoutError:
        signal.alarm(0)
        print("   SWIPE TIMEOUT")
    except Exception as e:
        signal.alarm(0)
        print(f"   SWIPE ERROR: {e}")

    time.sleep(1)

    print("5. mobile:doubleTap at center (like)...")
    signal.alarm(20)
    try:
        driver.execute_script("mobile: doubleTap", {"x": 187, "y": 406})
        signal.alarm(0)
        print("   DOUBLE-TAP OK!")
    except TimeoutError:
        signal.alarm(0)
        print("   DOUBLE-TAP TIMEOUT")
    except Exception as e:
        signal.alarm(0)
        print(f"   DOUBLE-TAP ERROR: {e}")

    time.sleep(1)

    print("6. screenshot (doesn't query views)...")
    signal.alarm(20)
    try:
        b64 = driver.get_screenshot_as_base64()
        signal.alarm(0)
        print(f"   SCREENSHOT OK: {len(b64)} bytes")
    except TimeoutError:
        signal.alarm(0)
        print("   SCREENSHOT TIMEOUT")
    except Exception as e:
        signal.alarm(0)
        print(f"   SCREENSHOT ERROR: {e}")

    time.sleep(1)

    # Try W3C Actions API (lower level touch)
    print("7. W3C Actions swipe (pointer move)...")
    signal.alarm(20)
    try:
        from selenium.webdriver.common.action_chains import ActionChains
        from selenium.webdriver.common.actions.pointer_input import PointerInput
        from selenium.webdriver import ActionBuilder
        from selenium.webdriver.common.actions import interaction

        actions = ActionBuilder(driver, mouse=PointerInput(interaction.POINTER_TOUCH, "finger"))
        actions.pointer_action.move_to_location(187, 600)
        actions.pointer_action.pointer_down()
        actions.pointer_action.move_to_location(187, 200)
        actions.pointer_action.pointer_up()
        actions.perform()
        signal.alarm(0)
        print("   W3C SWIPE OK!")
    except TimeoutError:
        signal.alarm(0)
        print("   W3C SWIPE TIMEOUT")
    except Exception as e:
        signal.alarm(0)
        print(f"   W3C SWIPE ERROR: {e}")

    print("\nAll tests done!")
    try:
        driver.quit()
    except:
        pass

if __name__ == "__main__":
    main()
