#!/usr/bin/env python3
"""Direct WDA test - correct endpoints for swipe/tap."""
import urllib.request, urllib.error, json, time

WDA = "http://192.168.1.49:8100"

def wda(method, path, data=None, timeout=15):
    url = f"{WDA}{path}"
    try:
        if data is not None:
            req = urllib.request.Request(url, data=json.dumps(data).encode(),
                                        headers={"Content-Type":"application/json"}, method=method)
        else:
            req = urllib.request.Request(url, method=method)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.URLError as e:
        if "timed out" in str(e).lower(): return {"_err":"TIMEOUT"}
        return {"_err":str(e)[:200]}
    except Exception as e:
        return {"_err":str(e)[:200]}

def test(name, method, path, data=None):
    start = time.time()
    r = wda(method, path, data)
    elapsed = time.time() - start
    err = r.get("_err")
    if err:
        print(f"   {name}: FAIL ({elapsed:.1f}s) - {err}")
        return False
    else:
        print(f"   {name}: OK ({elapsed:.1f}s)")
        return True

# Get existing session or create one
print("Checking for existing session...")
r = wda("GET", "/status")
sid = r.get("value",{}).get("sessionId")
if not sid:
    print("Creating session with Settings...")
    r = wda("POST", "/session", {"capabilities":{"alwaysMatch":{"bundleId":"com.apple.Preferences","shouldWaitForQuiescence":False}}})
    sid = r.get("value",{}).get("sessionId")
print(f"Session: {sid}")

# Set snapshotMaxDepth
wda("POST", f"/session/{sid}/appium/settings", {"settings":{"snapshotMaxDepth":10,"customSnapshotTimeout":5,"animationCoolOffTimeout":0}})

# Activate TikTok
print("\nActivating TikTok...")
wda("POST", f"/session/{sid}/wda/apps/launch", {"bundleId":"com.zhiliaoapp.musically"})
time.sleep(3)

print("\n=== Testing tap/swipe endpoints ===")

# Try various swipe endpoints
print("\n--- Swipe endpoints ---")
test("POST /wda/dragfromtoforduration", "POST", f"/session/{sid}/wda/dragfromtoforduration",
     {"fromX":187,"fromY":600,"toX":187,"toY":200,"duration":0.5})
time.sleep(1)

test("POST /wda/element/0/dragfromtoforduration", "POST", f"/session/{sid}/wda/element/0/dragfromtoforduration",
     {"fromX":187,"fromY":600,"toX":187,"toY":200,"duration":0.5})
time.sleep(1)

# W3C Actions (the standard way)
print("\n--- W3C Actions (swipe) ---")
test("POST /actions (swipe)", "POST", f"/session/{sid}/actions", {
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
})
time.sleep(2)

# Tap endpoints
print("\n--- Tap endpoints ---")
test("POST /wda/tap (no element)", "POST", f"/session/{sid}/wda/tap/null",
     {"x":187,"y":406})
time.sleep(1)

# W3C Actions (tap)
test("POST /actions (tap)", "POST", f"/session/{sid}/actions", {
    "actions": [{
        "type": "pointer",
        "id": "finger1",
        "parameters": {"pointerType": "touch"},
        "actions": [
            {"type": "pointerMove", "duration": 0, "x": 187, "y": 406},
            {"type": "pointerDown", "button": 0},
            {"type": "pause", "duration": 50},
            {"type": "pointerUp", "button": 0}
        ]
    }]
})
time.sleep(1)

# Double tap (already works)
test("POST /wda/doubleTap", "POST", f"/session/{sid}/wda/doubleTap",
     {"x":187,"y":406})
time.sleep(1)

# Another swipe with W3C actions
print("\n--- Final swipe ---")
test("POST /actions (swipe 2)", "POST", f"/session/{sid}/actions", {
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
})

# Screenshot
print("\n--- Screenshot ---")
start = time.time()
r = wda("GET", f"/session/{sid}/screenshot", timeout=10)
v = r.get("value","")
if isinstance(v,str) and len(v)>100:
    import base64
    with open("/Users/jean/tiktok-warmup/tiktok_proof.png","wb") as f:
        f.write(base64.b64decode(v))
    print(f"   screenshot: OK ({time.time()-start:.1f}s) saved tiktok_proof.png")
else:
    print(f"   screenshot: {str(v)[:100]}")

print("\n=== DONE ===")
wda("DELETE", f"/session/{sid}")
