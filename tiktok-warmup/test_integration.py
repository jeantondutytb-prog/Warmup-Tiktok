#!/usr/bin/env python3
"""Integration test: use the actual app classes to scroll/like TikTok."""
import sys, time
sys.path.insert(0, "/Users/jean/tiktok-warmup")

from app.core.appium_driver import AppiumDriverManager

print("=== Integration test ===")
print("1. Creating WDA session...")
mgr = AppiumDriverManager()
driver = mgr.create_session({}, "test")
print(f"   Session: {driver.session_id}")
print(f"   Window: {driver.get_window_size()}")

print("\n2. Swipe (scroll feed)...")
driver.execute_script("mobile: swipe", {"direction": "up", "velocity": 1500})
print("   OK")
time.sleep(2)

print("\n3. Double-tap (like)...")
driver.execute_script("mobile: doubleTap", {"x": 187, "y": 406})
print("   OK")
time.sleep(1)

print("\n4. Swipe again...")
driver.execute_script("mobile: swipe", {"direction": "up", "velocity": 1200})
print("   OK")
time.sleep(2)

print("\n5. Tap (follow button area)...")
driver.execute_script("mobile: tap", {"x": 345, "y": 292})
print("   OK")
time.sleep(1)

print("\n6. Swipe again...")
driver.execute_script("mobile: swipe", {"direction": "up", "velocity": 1800})
print("   OK")
time.sleep(1)

print("\n7. Screenshot...")
b64 = driver.get_screenshot_as_base64()
print(f"   {len(b64)} chars")

import base64
with open("/Users/jean/tiktok-warmup/integration_proof.png", "wb") as f:
    f.write(base64.b64decode(b64))
print("   Saved integration_proof.png")

print("\n8. Cleanup...")
mgr.close_session(driver)
print("   Done!")
print("\n*** INTEGRATION TEST PASSED ***")
