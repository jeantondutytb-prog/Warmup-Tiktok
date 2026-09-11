#!/usr/bin/env python3
"""Follow 40 commenters on Trend 10k videos, for each account."""
import json, time, base64, io, urllib.request, sys
from PIL import Image

WDA = "http://169.254.140.1:8100"
SID = open("/tmp/wda_sid.txt").read().strip()
W, H = 375, 812

ACCOUNTS = [
    {"username": "jeanzdozzr", "row": 0},
    {"username": "comptoxltmg", "row": 1},
    {"username": "ambrezsgs0i", "row": 2},
    {"username": "alicevuum5e", "row": 3},
]

TARGET_FOLLOWS = 40

def req(method, path, data=None):
    url = f"{WDA}{path}"
    r = urllib.request.Request(url, method=method)
    if data:
        r = urllib.request.Request(url, json.dumps(data).encode(),
            {"Content-Type": "application/json"}, method=method)
    return json.loads(urllib.request.urlopen(r, timeout=15).read())

def tap(x, y):
    req("POST", f"/session/{SID}/actions", {"actions": [{"type":"pointer","id":"f1",
        "parameters":{"pointerType":"touch"},"actions":[
        {"type":"pointerMove","duration":0,"x":x,"y":y},
        {"type":"pointerDown","button":0},
        {"type":"pointerUp","button":0}]}]})

def swipe(fx, fy, tx, ty, ms=300):
    req("POST", f"/session/{SID}/actions", {"actions": [{"type":"pointer","id":"f1",
        "parameters":{"pointerType":"touch"},"actions":[
        {"type":"pointerMove","duration":0,"x":fx,"y":fy},
        {"type":"pointerDown","button":0},
        {"type":"pointerMove","duration":ms,"x":tx,"y":ty,"origin":"viewport"},
        {"type":"pointerUp","button":0}]}]})

def shot():
    r = req("GET", f"/session/{SID}/screenshot")
    return Image.open(io.BytesIO(base64.b64decode(r["value"])))

def back():
    swipe(3, 400, 280, 400, 300)
    time.sleep(1.5)

def home():
    req("POST", f"/session/{SID}/wda/pressButton", {"name": "home"})
    time.sleep(0.5)

def launch_tiktok():
    req("POST", f"/session/{SID}/wda/apps/launch", {"bundleId": "com.zhiliaoapp.musically"})
    time.sleep(3)

def kill_tiktok():
    req("POST", f"/session/{SID}/wda/apps/terminate", {"bundleId": "com.zhiliaoapp.musically"})
    time.sleep(1)

def has_comments(img):
    w, h = img.size
    n = 0
    for y in range(h//3, 2*h//3, 10):
        r, g, b = img.getpixel((w//2, y))[:3]
        if r > 240 and g > 240 and b > 240:
            n += 1
    return n > 8

def scroll_comments():
    swipe(187, 600, 187, 380, 350)
    time.sleep(1.2)

def find_suivre(img):
    """Find red Suivre button, only in upper 300pt to avoid suggested accounts."""
    w, h = img.size
    in_red = False
    sy = 0
    for y in range(200, 900, 3):
        r, g, b = img.getpixel((w//2, y))[:3]
        if r > 200 and g < 100 and b < 100:
            if not in_red:
                in_red = True
                sy = y
        elif in_red:
            in_red = False
            if y - sy > 50:
                cy = (sy + y) // 2
                lx, rx = w//2, w//2
                for x in range(0, w, 3):
                    rr, gg, bb = img.getpixel((x, cy))[:3]
                    if rr > 200 and gg < 100 and bb < 100:
                        lx = x; break
                for x in range(w-1, 0, -3):
                    rr, gg, bb = img.getpixel((x, cy))[:3]
                    if rr > 200 and gg < 100 and bb < 100:
                        rx = x; break
                if rx - lx > 150:
                    return ((lx+rx)//2//3, cy//3)
    return None

def find_comment_icon_y(img):
    """Find the comment icon Y position by scanning the right sidebar."""
    w, h = img.size
    # Scan at x near right edge for white icon clusters
    scan_x = w - 110  # ~338pt area
    clusters = []
    in_white = False
    sy = 0
    for y in range(400, 1800, 2):
        r, g, b = img.getpixel((scan_x, y))[:3]
        if (r+g+b)/3 > 230:
            if not in_white:
                in_white = True
                sy = y
        elif in_white:
            in_white = False
            hh = y - sy
            if 15 < hh < 120:
                clusters.append(((sy+y)//2//3, hh))
    # The comment icon is typically the one AFTER the heart
    # Return the second cluster y if available
    if len(clusters) >= 2:
        return clusters[1][0]  # Second icon = comment
    elif len(clusters) >= 1:
        return clusters[0][0]
    return 370  # fallback

def open_comments(max_tries=3):
    """Try to open the comments panel."""
    for attempt in range(max_tries):
        img = shot()
        if has_comments(img):
            # Dismiss any keyboard by tapping video area
            tap(187, 200)
            time.sleep(0.5)
            return True
        
        # Find comment icon position
        comment_y = find_comment_icon_y(img)
        print(f"  Comment icon estimated at y={comment_y}, tapping...")
        tap(338, comment_y)
        time.sleep(2.5)
        
        img = shot()
        if has_comments(img):
            tap(187, 200)  # Dismiss keyboard if triggered
            time.sleep(0.5)
            return True
        
        # Might have opened profile instead - go back
        back()
        time.sleep(1)
    
    return False

def find_top_level_avatars(img):
    """Find top-level comment avatar Y positions (not replies)."""
    w, h = img.size
    rows = []
    
    # Top-level avatars are at x ≈ 55px (18pt)
    # Replies are indented to x ≈ 105px (35pt)
    # We check x=55 for top-level only
    
    # Find panel top
    panel_top = None
    for y in range(h//4, h, 5):
        r, g, b = img.getpixel((55, y))[:3]
        if (r+g+b)/3 > 240:
            panel_top = y
            break
    if not panel_top:
        # Try w//4 as x
        for y in range(h//4, h, 5):
            r, g, b = img.getpixel((w//4, y))[:3]
            if (r+g+b)/3 > 240:
                panel_top = y
                break
    if not panel_top:
        return []
    
    start_y = panel_top + 80
    end_y = h - 300
    
    in_dark = False
    sy = 0
    for y in range(start_y, end_y, 2):
        r, g, b = img.getpixel((55, y))[:3]
        if (r+g+b)/3 < 220:
            if not in_dark:
                in_dark = True
                sy = y
        elif in_dark:
            in_dark = False
            hh = y - sy
            if 25 < hh < 150:
                cy = (sy + y) // 2
                pt = cy // 3
                if not any(abs(pt - e) < 20 for e in rows):
                    rows.append(pt)
    
    return rows

def try_follow_commenter(y_pt):
    """Try to follow commenter at y position. Returns True if followed."""
    # Try x=63 first (works for top-level comments)
    tap(63, y_pt)
    time.sleep(2.5)
    
    img = shot()
    btn = find_suivre(img)
    if btn:
        tap(btn[0], btn[1])
        time.sleep(1)
        back()
        return True
    
    # Check if on a profile without Suivre (already following)
    if not has_comments(img):
        back()
        time.sleep(1)
        return False  # Already following or error
    
    # Still on comments - try slightly different x
    tap(50, y_pt)
    time.sleep(2.5)
    
    img = shot()
    btn = find_suivre(img)
    if btn:
        tap(btn[0], btn[1])
        time.sleep(1)
        back()
        return True
    
    if not has_comments(img):
        back()
        time.sleep(1)
    
    return False

def switch_account(row_index):
    """Switch to TikTok account by row index in the account switcher."""
    # Tap Profil tab
    tap(int(W * 0.90), int(H * 0.97))
    time.sleep(2)
    
    # Tap username at top to open account switcher
    tap(int(W * 0.40), int(H * 0.16))
    time.sleep(2)
    
    # Tap the account row
    row_y = 0.65 + row_index * 0.085
    tap(int(W * 0.40), int(H * row_y))
    time.sleep(3)
    
    # Go to Accueil
    tap(int(W * 0.10), int(H * 0.97))
    time.sleep(2)

def search_trend_10k():
    """Search for trend 10k and open a video."""
    # Tap search icon (top right on Pour toi)
    tap(355, 50)
    time.sleep(2)
    
    # Type "trend 10k" in search
    img = shot()
    # Find the search field and type
    try:
        result = req("POST", f"/session/{SID}/element", {
            "using": "class chain",
            "value": "**/XCUIElementTypeSearchField"
        })
        eid = result.get("value", {}).get("ELEMENT") or result.get("value", {}).get("element-6066-11e4-a52e-4f735466cecf")
        if eid:
            req("POST", f"/session/{SID}/element/{eid}/value", {"text": "trend 10k", "value": list("trend 10k")})
            time.sleep(1)
            # Tap search/return
            tap(350, 50)  # Search button
            time.sleep(2)
    except:
        # Fallback: tap search bar area and type
        tap(187, 60)
        time.sleep(1)
        # Try typing via keyboard
        for char in "trend 10k":
            try:
                result = req("POST", f"/session/{SID}/element", {
                    "using": "class chain",
                    "value": "**/XCUIElementTypeSearchField"
                })
                eid = result.get("value", {}).get("ELEMENT") or result.get("value", {}).get("element-6066-11e4-a52e-4f735466cecf")
                if eid:
                    req("POST", f"/session/{SID}/element/{eid}/value", {"text": char, "value": [char]})
            except:
                pass
            time.sleep(0.1)
        time.sleep(1)
    
    # Tap "Rechercher" / search button
    tap(350, 50)
    time.sleep(3)
    
    # Should see search results. Tap "Vidéos" tab if available
    # Then tap the first video
    tap(187, 400)  # Tap first result
    time.sleep(3)

def follow_commenters_loop(account_name, target=40):
    """Main loop: follow commenters on the current video."""
    followed = 0
    rounds = 0
    max_rounds = target * 3  # Allow plenty of rounds
    
    while followed < target and rounds < max_rounds:
        rounds += 1
        
        img = shot()
        if not has_comments(img):
            if not open_comments():
                print(f"  [{account_name}] Can't open comments, stopping")
                break
            img = shot()
        
        rows = find_top_level_avatars(img)
        
        if not rows:
            scroll_comments()
            continue
        
        for y_pt in rows:
            if followed >= target:
                break
            
            if try_follow_commenter(y_pt):
                followed += 1
                print(f"  [{account_name}] Followed #{followed}")
            
            time.sleep(0.3)
            
            # Check we're still on comments
            img = shot()
            if not has_comments(img):
                if not open_comments():
                    break
        
        scroll_comments()
    
    return followed

def main():
    total_followed = {}
    
    for acc in ACCOUNTS:
        name = acc["username"]
        row = acc["row"]
        
        print(f"\n{'='*50}")
        print(f"Account: {name} (row {row})")
        print(f"{'='*50}")
        
        # Switch account
        print(f"Switching to {name}...")
        switch_account(row)
        time.sleep(2)
        
        # Search trend 10k
        print("Searching 'trend 10k'...")
        search_trend_10k()
        time.sleep(2)
        
        # Open comments
        print("Opening comments...")
        if not open_comments():
            print(f"Failed to open comments for {name}, skipping")
            # Go back to feed
            kill_tiktok()
            launch_tiktok()
            total_followed[name] = 0
            continue
        
        # Follow loop
        print(f"Starting follow loop (target: {TARGET_FOLLOWS})...")
        count = follow_commenters_loop(name, TARGET_FOLLOWS)
        total_followed[name] = count
        print(f"Followed {count} for {name}")
        
        # Go back to feed for next account
        kill_tiktok()
        launch_tiktok()
    
    print(f"\n{'='*50}")
    print("SUMMARY")
    print(f"{'='*50}")
    for name, count in total_followed.items():
        print(f"  {name}: {count} followed")
    print(f"  Total: {sum(total_followed.values())}")

if __name__ == "__main__":
    main()
