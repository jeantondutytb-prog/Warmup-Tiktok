"""Debug script to see TikTok profile page layout on iPhone."""
import json
import subprocess
import tempfile
import base64
import os
from appium import webdriver
from appium.options.ios import XCUITestOptions

TEAM_ID = "U284BGAVKL"
WDA_BUNDLE_ID = "com.jean.wda.runner"
DERIVED_DATA = "/Users/jean/Library/Developer/Xcode/DerivedData/WebDriverAgent-entqkdybqjzegiahlgkxvxghpzdf"


def get_udid():
    tmp = tempfile.mktemp(suffix=".json")
    subprocess.run(
        ["xcrun", "devicectl", "list", "devices", "--json-output", tmp],
        capture_output=True, text=True,
    )
    with open(tmp) as f:
        data = json.load(f)
    os.unlink(tmp)
    for d in data.get("result", {}).get("devices", []):
        hw = d.get("hardwareProperties", {})
        conn = d.get("connectionProperties", {})
        dev = d.get("deviceProperties", {})
        if (hw.get("deviceType") == "iPhone"
                and conn.get("pairingState") == "paired"
                and dev.get("bootState") == "booted"):
            return hw.get("udid")
    return None


udid = get_udid()
if not udid:
    print("No iPhone found!")
    exit(1)
print(f"iPhone UDID: {udid}")

opts = XCUITestOptions()
opts.udid = udid
opts.platform_name = "iOS"
opts.automation_name = "XCUITest"
opts.bundle_id = "com.zhiliaoapp.musically"
opts.no_reset = True
opts.xcode_org_id = TEAM_ID
opts.xcode_signing_id = "Apple Development"
opts.use_prebuilt_wda = True
opts.derived_data_path = DERIVED_DATA
opts.updated_wda_bundle_id = WDA_BUNDLE_ID
opts.wda_launch_timeout = 120000
opts.set_capability("appium:showXcodeLog", True)

print("Creating Appium session...")
driver = webdriver.Remote("http://localhost:4723", options=opts)
size = driver.get_window_size()
print(f"Screen: {size}")

# Screenshot from feed
ss = driver.get_screenshot_as_base64()
with open("/Users/jean/tiktok-warmup/debug_feed.png", "wb") as f:
    f.write(base64.b64decode(ss))
print("Saved: debug_feed.png")

# Tap Profile tab
import time
profile_x = int(size["width"] * 0.90)
profile_y = int(size["height"] * 0.97)
print(f"Tapping Profile tab at ({profile_x}, {profile_y})...")
driver.execute_script("mobile: tap", {"x": profile_x, "y": profile_y})
time.sleep(3)

# Screenshot of profile page
ss = driver.get_screenshot_as_base64()
with open("/Users/jean/tiktok-warmup/debug_profile.png", "wb") as f:
    f.write(base64.b64decode(ss))
print("Saved: debug_profile.png")

# Get page source to find elements
source = driver.page_source
with open("/Users/jean/tiktok-warmup/debug_source.xml", "w") as f:
    f.write(source)
print("Saved: debug_source.xml (full page source)")

# Print elements that might be the username
from xml.etree import ElementTree
root = ElementTree.fromstring(source)
print("\n=== Elements near top of screen (y < 150) ===")
for elem in root.iter():
    x = elem.get("x")
    y = elem.get("y")
    label = elem.get("label", "")
    name = elem.get("name", "")
    etype = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
    if y and int(y) < 150 and (label or name):
        print(f"  type={etype} x={x} y={y} w={elem.get('width')} h={elem.get('height')} label='{label}' name='{name}'")

# Now tap where we think the username is (50%, 12%)
tap_x = int(size["width"] * 0.40)
tap_y = int(size["height"] * 0.16)
print(f"\nTapping username area at ({tap_x}, {tap_y})...")
driver.execute_script("mobile: tap", {"x": tap_x, "y": tap_y})
time.sleep(2)

# Screenshot of switcher (hopefully)
ss = driver.get_screenshot_as_base64()
with open("/Users/jean/tiktok-warmup/debug_switcher.png", "wb") as f:
    f.write(base64.b64decode(ss))
print("Saved: debug_switcher.png")

# Page source of switcher
source2 = driver.page_source
with open("/Users/jean/tiktok-warmup/debug_switcher_source.xml", "w") as f:
    f.write(source2)
print("Saved: debug_switcher_source.xml")

# Look for account-related elements
root2 = ElementTree.fromstring(source2)
print("\n=== Elements with account-like labels ===")
for elem in root2.iter():
    label = elem.get("label", "")
    name = elem.get("name", "")
    val = elem.get("value", "")
    etype = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
    for username in ["jeanzdozzr", "ambrezsgs0i", "alicevuum5e", "comptoxltmg"]:
        if username in label or username in name or username in val:
            print(f"  FOUND: type={etype} x={elem.get('x')} y={elem.get('y')} w={elem.get('width')} h={elem.get('height')} label='{label}' name='{name}'")
            break

driver.quit()
print("\nDone!")
