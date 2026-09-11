#!/usr/bin/env python3
"""Direct WDA test via HTTP - no Appium, no dependencies."""
import urllib.request, urllib.error, json, time

WDA = "http://192.168.1.49:8100"

def wda(method, path, data=None, timeout=15):
    url = f"{WDA}{path}"
    try:
        if data is not None:
            req = urllib.request.Request(url, data=json.dumps(data).encode(), 
                                        headers={"Content-Type": "application/json"},
                                        method=method)
        else:
            req = urllib.request.Request(url, method=method)
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read())
    except urllib.error.URLError as e:
        if "timed out" in str(e).lower():
            return {"error": "TIMEOUT"}
        return {"error": str(e)[:200]}
    except Exception as e:
        return {"error": str(e)[:200]}

# 1. Status
print("1. WDA status:")
s = wda("GET", "/status")
print(f"   {s.get('value',{}).get('message','?')}")

# 2. Create session with Settings
print("\n2. Session (Settings)...")
r = wda("POST", "/session", {
    "capabilities": {
        "alwaysMatch": {
            "bundleId": "com.apple.Preferences",
            "shouldWaitForQuiescence": False,
        }
    }
})
sid = r.get("value",{}).get("sessionId") or r.get("sessionId")
if not sid:
    print(f"   FAIL: {r}")
    exit(1)
print(f"   Session: {sid}")

# 3. snapshotMaxDepth
print("\n3. snapshotMaxDepth=10...")
wda("POST", f"/session/{sid}/appium/settings", {"settings":{"snapshotMaxDepth":10,"customSnapshotTimeout":5,"animationCoolOffTimeout":0}})
print("   OK")

# 4. Window size
print("\n4. Window size:")
r = wda("GET", f"/session/{sid}/window/size")
print(f"   {r.get('value',r)}")

# 5. Activate TikTok
print("\n5. Activate TikTok...")
r = wda("POST", f"/session/{sid}/wda/apps/launch", {"bundleId":"com.zhiliaoapp.musically"})
print(f"   {r.get('value',r)}")
time.sleep(3)

# 6. Swipe
print("\n6. Swipe up...")
start = time.time()
r = wda("POST", f"/session/{sid}/wda/element/0/swipe", {"direction":"up","velocity":1500})
print(f"   ({time.time()-start:.1f}s) {json.dumps(r)[:100]}")
time.sleep(2)

# 7. Tap
print("\n7. Tap...")
start = time.time()
r = wda("POST", f"/session/{sid}/wda/tap/0", {"x":187,"y":406})
print(f"   ({time.time()-start:.1f}s) {json.dumps(r)[:100]}")
time.sleep(1)

# 8. Double tap
print("\n8. Double tap...")
start = time.time()
r = wda("POST", f"/session/{sid}/wda/doubleTap", {"x":187,"y":406})
print(f"   ({time.time()-start:.1f}s) {json.dumps(r)[:100]}")
time.sleep(1)

# 9. Swipe again
print("\n9. Swipe up again...")
start = time.time()
r = wda("POST", f"/session/{sid}/wda/element/0/swipe", {"direction":"up","velocity":1500})
print(f"   ({time.time()-start:.1f}s) {json.dumps(r)[:100]}")

# 10. Screenshot
print("\n10. Screenshot...")
start = time.time()
r = wda("GET", f"/session/{sid}/screenshot", timeout=10)
v = r.get("value","")
if isinstance(v,str) and len(v)>100:
    print(f"   ({time.time()-start:.1f}s) OK: {len(v)} chars")
else:
    print(f"   ({time.time()-start:.1f}s) {str(v)[:100]}")

print("\n=== DONE ===")
wda("DELETE", f"/session/{sid}")
