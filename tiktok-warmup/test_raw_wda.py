#!/usr/bin/env python3
"""
Test WDA directly through tunnel, bypassing Appium entirely.
Uses pymobiledevice3 to:
1. Start WDA via xcuitest service
2. Connect to WDA port through tunnel
3. Send raw HTTP commands to WDA
"""
import asyncio
import json
import time
import signal
import sys

async def main():
    from pymobiledevice3.remote.remote_service_discovery import RemoteServiceDiscoveryService
    from pymobiledevice3.services.testmanagerd import XCUITestService

    # Connect to device via tunnel
    tunnel_addr = "fd0a:dbae:c7e8::1"
    tunnel_port = 58640

    print(f"Connecting to RSD at [{tunnel_addr}]:{tunnel_port}...")
    rsd = RemoteServiceDiscoveryService((tunnel_addr, tunnel_port))
    await rsd.connect()
    print("RSD connected")

    # Check if WDA is already running by trying to connect to port 8100
    import aiohttp
    wda_url = f"http://[{tunnel_addr}]:8100"

    print(f"\n1. Checking WDA status at {wda_url}...")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{wda_url}/status", timeout=aiohttp.ClientTimeout(total=10)) as resp:
                data = await resp.json()
                print(f"   WDA already running: {json.dumps(data, indent=2)[:200]}")
    except Exception as e:
        print(f"   WDA not accessible: {e}")
        print("   (Need to start WDA through Appium first)")
        return

    # List existing sessions
    print("\n2. Listing WDA sessions...")
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{wda_url}/sessions", timeout=aiohttp.ClientTimeout(total=10)) as resp:
                data = await resp.json()
                sessions = data.get("value", [])
                print(f"   {len(sessions)} sessions found")
                for s in sessions:
                    sid = s.get("id", "?")
                    caps = s.get("capabilities", {})
                    bundle = caps.get("CFBundleIdentifier", "?")
                    print(f"   - {sid}: {bundle}")
    except Exception as e:
        print(f"   Error: {e}")
        return

    if not sessions:
        # Create a new session with Settings
        print("\n3. Creating WDA session with Settings...")
        payload = {
            "capabilities": {
                "alwaysMatch": {
                    "bundleId": "com.apple.Preferences",
                    "shouldWaitForQuiescence": False,
                }
            }
        }
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(f"{wda_url}/session", json=payload, timeout=aiohttp.ClientTimeout(total=30)) as resp:
                    data = await resp.json()
                    session_id = data.get("value", {}).get("sessionId") or data.get("sessionId")
                    print(f"   Session created: {session_id}")
        except Exception as e:
            print(f"   Error: {e}")
            return
    else:
        session_id = sessions[0].get("id")
        print(f"\n3. Using existing session: {session_id}")

    # Get window size (should work with Settings)
    print("\n4. get_window_size (Settings)...")
    try:
        async with aiohttp.ClientSession() as http:
            async with http.get(f"{wda_url}/session/{session_id}/window/rect", timeout=aiohttp.ClientTimeout(total=15)) as resp:
                data = await resp.json()
                print(f"   OK: {data.get('value', {})}")
    except Exception as e:
        print(f"   Error: {e}")

    # Activate TikTok
    print("\n5. Activating TikTok...")
    try:
        async with aiohttp.ClientSession() as http:
            async with http.post(f"{wda_url}/session/{session_id}/wda/apps/activate",
                               json={"bundleId": "com.zhiliaoapp.musically"},
                               timeout=aiohttp.ClientTimeout(total=15)) as resp:
                data = await resp.json()
                print(f"   OK: {data.get('value')}")
    except Exception as e:
        print(f"   Error: {e}")
        return

    await asyncio.sleep(3)
    print("   TikTok should be visible now")

    # Try swipe via WDA directly — raw W3C Actions
    print("\n6. Sending W3C Actions swipe DIRECTLY to WDA...")
    actions_payload = {
        "actions": [{
            "type": "pointer",
            "id": "finger1",
            "parameters": {"pointerType": "touch"},
            "actions": [
                {"type": "pointerMove", "duration": 0, "x": 187, "y": 600},
                {"type": "pointerDown", "button": 0},
                {"type": "pause", "duration": 100},
                {"type": "pointerMove", "duration": 300, "x": 187, "y": 200, "origin": "viewport"},
                {"type": "pointerUp", "button": 0}
            ]
        }]
    }
    try:
        async with aiohttp.ClientSession() as http:
            async with http.post(f"{wda_url}/session/{session_id}/actions",
                               json=actions_payload,
                               timeout=aiohttp.ClientTimeout(total=20)) as resp:
                data = await resp.json()
                status = data.get("value")
                if status is None or status == {}:
                    print(f"   SWIPE OK! Response: {data}")
                else:
                    print(f"   Response: {json.dumps(data, indent=2)[:500]}")
    except asyncio.TimeoutError:
        print("   TIMEOUT (20s) — WDA hung on swipe command")
    except Exception as e:
        print(f"   Error: {type(e).__name__}: {e}")

    # Try /wda/touch/perform (older API)
    print("\n7. Trying /wda/touch/perform (older touch API)...")
    touch_payload = {
        "actions": [
            {"action": "press", "options": {"x": 187, "y": 600}},
            {"action": "wait", "options": {"ms": 200}},
            {"action": "moveTo", "options": {"x": 187, "y": 200}},
            {"action": "release"}
        ]
    }
    try:
        async with aiohttp.ClientSession() as http:
            async with http.post(f"{wda_url}/session/{session_id}/wda/touch/perform",
                               json=touch_payload,
                               timeout=aiohttp.ClientTimeout(total=20)) as resp:
                data = await resp.json()
                print(f"   Response: {json.dumps(data, indent=2)[:500]}")
    except asyncio.TimeoutError:
        print("   TIMEOUT (20s)")
    except Exception as e:
        print(f"   Error: {type(e).__name__}: {e}")

    # Try pressButton (which we know works)
    print("\n8. pressButton volumeUp (known to work)...")
    try:
        async with aiohttp.ClientSession() as http:
            async with http.post(f"{wda_url}/session/{session_id}/wda/pressButton",
                               json={"name": "volumeUp"},
                               timeout=aiohttp.ClientTimeout(total=15)) as resp:
                data = await resp.json()
                print(f"   Response: {json.dumps(data, indent=2)[:200]}")
    except asyncio.TimeoutError:
        print("   TIMEOUT")
    except Exception as e:
        print(f"   Error: {type(e).__name__}: {e}")

    # Try screenshot
    print("\n9. Screenshot...")
    try:
        async with aiohttp.ClientSession() as http:
            async with http.get(f"{wda_url}/screenshot",
                               timeout=aiohttp.ClientTimeout(total=15)) as resp:
                data = await resp.json()
                b64 = data.get("value", "")
                print(f"   Screenshot: {len(b64)} chars")
    except asyncio.TimeoutError:
        print("   TIMEOUT")
    except Exception as e:
        print(f"   Error: {type(e).__name__}: {e}")

    print("\nDone!")

if __name__ == "__main__":
    asyncio.run(main())
