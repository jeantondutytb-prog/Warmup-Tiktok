#!/usr/bin/env python3
"""
Create an Appium session with Settings, then test raw WDA commands
through the tunnel with aiohttp, bypassing Appium for the actual commands.
"""
import json, subprocess, tempfile, time, signal, sys, asyncio
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

async def test_raw_wda(session_id):
    """Send raw HTTP commands to WDA through Appium's proxy."""
    import aiohttp

    # We connect to Appium which proxies to WDA
    base_url = "http://localhost:4723"

    # Activate TikTok
    print("\n4. Activating TikTok via Appium proxy...")
    try:
        async with aiohttp.ClientSession() as http:
            async with http.post(
                f"{base_url}/session/{session_id}/appium/device/activate_app",
                json={"bundleId": "com.zhiliaoapp.musically"},
                timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                data = await resp.json()
                print(f"   OK: status {resp.status}")
    except Exception as e:
        print(f"   Error: {e}")
        return

    await asyncio.sleep(3)

    # Try pressButton (known working)
    print("\n5. pressButton volumeUp...")
    try:
        async with aiohttp.ClientSession() as http:
            async with http.post(
                f"{base_url}/session/{session_id}/execute/sync",
                json={"script": "mobile: pressButton", "args": [{"name": "volumeUp"}]},
                timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                data = await resp.json()
                err = data.get("value", {})
                if isinstance(err, dict) and err.get("error"):
                    print(f"   Error: {err.get('message', '')[:100]}")
                else:
                    print(f"   OK!")
    except asyncio.TimeoutError:
        print("   TIMEOUT")
    except Exception as e:
        print(f"   Error: {e}")

    # Try mobile:tap with short timeout
    print("\n6. mobile:tap (x=187, y=406) with 15s timeout...")
    try:
        async with aiohttp.ClientSession() as http:
            async with http.post(
                f"{base_url}/session/{session_id}/execute/sync",
                json={"script": "mobile: tap", "args": [{"x": 187, "y": 406}]},
                timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                data = await resp.json()
                err = data.get("value", {})
                if isinstance(err, dict) and err.get("error"):
                    print(f"   Error: {err.get('message', '')[:200]}")
                else:
                    print(f"   TAP OK!")
    except asyncio.TimeoutError:
        print("   TIMEOUT (15s) — confirmed: touch hangs with TikTok")
    except Exception as e:
        print(f"   Error: {type(e).__name__}: {e}")

    # Try mobile:swipe with short timeout
    print("\n7. mobile:swipe up with 15s timeout...")
    try:
        async with aiohttp.ClientSession() as http:
            async with http.post(
                f"{base_url}/session/{session_id}/execute/sync",
                json={"script": "mobile: swipe", "args": [{"direction": "up", "velocity": 1500}]},
                timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                data = await resp.json()
                err = data.get("value", {})
                if isinstance(err, dict) and err.get("error"):
                    print(f"   Error: {err.get('message', '')[:200]}")
                else:
                    print(f"   SWIPE OK!")
    except asyncio.TimeoutError:
        print("   TIMEOUT (15s)")
    except Exception as e:
        print(f"   Error: {type(e).__name__}: {e}")

    # Try performIoHidEvent with touch screen HID codes
    # HID Usage Page for Digitizer: 0x0D, Usage ID for Touch Screen: 0x04
    print("\n8. performIoHidEvent (touch digitizer, may not work)...")
    try:
        async with aiohttp.ClientSession() as http:
            async with http.post(
                f"{base_url}/session/{session_id}/execute/sync",
                json={"script": "mobile: performIoHidEvent", "args": [{"page": 0x0C, "usage": 0x40, "durationSeconds": 0.005}]},
                timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                data = await resp.json()
                err = data.get("value", {})
                if isinstance(err, dict) and err.get("error"):
                    print(f"   Error: {err.get('message', '')[:200]}")
                else:
                    print(f"   HID Event OK! (home button via HID)")
    except asyncio.TimeoutError:
        print("   TIMEOUT")
    except Exception as e:
        print(f"   Error: {type(e).__name__}: {e}")

    # Now go back to TikTok after home press and try screenshot
    print("\n9. Re-activating TikTok...")
    try:
        async with aiohttp.ClientSession() as http:
            async with http.post(
                f"{base_url}/session/{session_id}/appium/device/activate_app",
                json={"bundleId": "com.zhiliaoapp.musically"},
                timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                print(f"   Status: {resp.status}")
    except Exception as e:
        print(f"   Error: {e}")

    await asyncio.sleep(2)

    print("\n10. Screenshot (while on TikTok)...")
    try:
        async with aiohttp.ClientSession() as http:
            async with http.get(
                f"{base_url}/session/{session_id}/screenshot",
                timeout=aiohttp.ClientTimeout(total=15)
            ) as resp:
                data = await resp.json()
                b64 = data.get("value", "")
                if isinstance(b64, str) and len(b64) > 100:
                    print(f"   SCREENSHOT OK: {len(b64)} chars")
                    # Save it
                    import base64
                    with open("/Users/jean/tiktok-warmup/tiktok_screenshot.png", "wb") as f:
                        f.write(base64.b64decode(b64))
                    print("   Saved to tiktok_screenshot.png")
                else:
                    print(f"   Response: {str(b64)[:200]}")
    except asyncio.TimeoutError:
        print("   TIMEOUT")
    except Exception as e:
        print(f"   Error: {type(e).__name__}: {e}")

def main():
    udid = get_udid()
    print(f"iPhone: {udid}")
    signal.signal(signal.SIGALRM, timeout_handler)

    # Create session with Settings
    options = XCUITestOptions()
    options.platform_name = "iOS"
    options.udid = udid
    options.bundle_id = "com.apple.Preferences"
    options.no_reset = True
    options.new_command_timeout = 600  # Long timeout so session doesn't expire
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
    print(f"2. Window: {size}")

    session_id = driver.session_id
    print(f"3. Session ID: {session_id}")

    # Run async tests
    asyncio.run(test_raw_wda(session_id))

    print("\nCleaning up...")
    try:
        driver.quit()
    except:
        pass
    print("Done!")

if __name__ == "__main__":
    main()
