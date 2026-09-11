#!/usr/bin/env python3
"""Follow commenters — simple version that just works."""
import json, time, base64, io, urllib.request
from PIL import Image

WDA = "http://169.254.140.1:8100"
SID = open("/tmp/wda_sid.txt").read().strip()

followed = 0
MAX = 50

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
    time.sleep(2)

def scroll_comments():
    swipe(187, 600, 187, 400, 350)
    time.sleep(1.5)

def has_comments(img):
    w, h = img.size
    n = 0
    for y in range(h//3, 2*h//3, 10):
        r, g, b = img.getpixel((w//2, y))[:3]
        if r > 240 and g > 240 and b > 240:
            n += 1
    return n > 8

def find_suivre(img):
    """Find red Suivre button, ignoring suggested accounts area."""
    w, h = img.size
    in_red = False
    sy = 0
    for y in range(200, 900, 3):  # Only scan upper part (< 300 points)
        r, g, b = img.getpixel((w//2, y))[:3]
        if r > 200 and g < 100 and b < 100:
            if not in_red:
                in_red = True
                sy = y
        elif in_red:
            in_red = False
            if y - sy > 50:
                cy = (sy + y) // 2
                # Check width
                lx, rx = w//2, w//2
                for x in range(0, w, 3):
                    rr, gg, bb = img.getpixel((x, cy))[:3]
                    if rr > 200 and gg < 100 and bb < 100:
                        lx = x; break
                for x in range(w-1, 0, -3):
                    rr, gg, bb = img.getpixel((x, cy))[:3]
                    if rr > 200 and gg < 100 and bb < 100:
                        rx = x; break
                if rx - lx > 150:  # Wide button
                    return ((lx+rx)//2//3, cy//3)
    return None

def find_avatars(img):
    """Find avatar Y positions. Scan multiple x columns to catch all avatars."""
    w, h = img.size

    # Find where white panel starts
    panel_top = None
    for y in range(h//4, h, 5):
        r, g, b = img.getpixel((w//4, y))[:3]
        if (r+g+b)/3 > 240:
            panel_top = y
            break
    if not panel_top:
        return []

    # Scan multiple x values to find avatar circles
    all_regions = []
    for scan_x in [45, 55, 65, 75]:
        in_dark = False
        sy = 0
        for y in range(panel_top + 80, h - 300, 2):
            r, g, b = img.getpixel((scan_x, y))[:3]
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
                    all_regions.append(pt)

    # Deduplicate (merge points within 15pt)
    all_regions.sort()
    result = []
    for pt in all_regions:
        if not any(abs(pt - e) < 15 for e in result):
            result.append(pt)
    return result

def try_follow(y_pt):
    """Navigate to commenter profile, follow, come back."""
    global followed

    # Tap on avatar/username area — x=18pt hits the avatar directly
    print(f"  Tap avatar at (18, {y_pt})...")
    tap(18, y_pt)
    time.sleep(2.5)

    img = shot()

    # Did we navigate to a profile?
    btn = find_suivre(img)
    if btn:
        print(f"  Suivre at {btn} — tapping...")
        tap(btn[0], btn[1])
        time.sleep(1.2)
        followed += 1
        print(f"  *** FOLLOWED #{followed} ***")
        back()
        return "followed"

    # Maybe already following (no red button but on a profile page)
    # Check for white background in upper area (profile layout)
    w, h = img.size
    upper_white = 0
    for y in range(100, 500, 10):
        r, g, b = img.getpixel((w//2, y))[:3]
        if (r+g+b)/3 > 240:
            upper_white += 1
    if upper_white > 15:
        print(f"  Already following (no red button), going back")
        back()
        return "already"

    # Still on comments — tap didn't work
    if has_comments(img):
        print(f"  Tap didn't navigate, trying username area...")
        # Retry with x=63 (username area, worked before)
        tap(63, y_pt)
        time.sleep(2.5)
        img = shot()
        btn = find_suivre(img)
        if btn:
            print(f"  Suivre at {btn} — tapping...")
            tap(btn[0], btn[1])
            time.sleep(1.2)
            followed += 1
            print(f"  *** FOLLOWED #{followed} ***")
            back()
            return "followed"
        if has_comments(img):
            print(f"  Still on comments, skipping this row")
            return "skip"
        # On profile without Suivre
        back()
        return "already"

    print(f"  Unknown state, going back")
    back()
    return "unknown"


def main():
    global followed
    print(f"=== Follow commenters — target: {MAX} ===\n")

    for rnd in range(1, 80):
        if followed >= MAX:
            break

        print(f"\n--- Round {rnd} | followed: {followed} ---")
        img = shot()

        if not has_comments(img):
            print("Comments closed, trying to reopen...")
            tap(333, 370)
            time.sleep(2)
            tap(187, 250)  # dismiss keyboard
            time.sleep(1)
            img = shot()
            if not has_comments(img):
                print("Can't reopen comments. Stopping.")
                break

        rows = find_avatars(img)
        print(f"Avatars at points y: {rows}")

        if not rows:
            print("No avatars found, scrolling...")
            scroll_comments()
            continue

        for y_pt in rows:
            if followed >= MAX:
                break
            result = try_follow(y_pt)
            time.sleep(0.5)

            # Make sure we're back on comments
            img = shot()
            if not has_comments(img):
                print("Lost comments, recovering...")
                back()
                time.sleep(1)
                img = shot()
                if not has_comments(img):
                    tap(333, 370)
                    time.sleep(2)
                    tap(187, 250)
                    time.sleep(1)

        scroll_comments()

    print(f"\n=== DONE — followed {followed} ===")


if __name__ == "__main__":
    main()
