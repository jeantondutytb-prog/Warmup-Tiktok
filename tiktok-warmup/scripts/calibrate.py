"""Calibration des points de tap, avec l'iPhone branché.

L'UI de TikTok n'est pas lisible dans l'arbre d'accessibilité, donc chaque
repère de `config/coords.yaml` est une position à l'écran qu'il faut vérifier
à l'œil. Ce script fait l'aller-retour : capture, tape, recapture.

    python -m scripts.calibrate list
        Liste les points et leur état.

    python -m scripts.calibrate shot [nom]
        Capture l'écran dans calibration/<nom>.png.

    python -m scripts.calibrate probe search_icon
        Capture avant, tape le point, capture après. Compare les deux images
        pour savoir si le tap a atterri au bon endroit.

    python -m scripts.calibrate set search_icon 0.92 0.078
        Écrit la position dans coords.yaml et la marque calibrée.

    python -m scripts.calibrate pixel 345 62
        Convertit des pixels d'une capture en pourcentages.

La connexion passe en direct par WebDriverAgent, comme les scripts
follow_*.py : c'est le chemin qui marche sur cette machine. Démarre WDA, puis
mets l'identifiant de session dans /tmp/wda_sid.txt.
"""

import base64
import json
import os
import sys
import time
import urllib.request

CONFIG = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "coords.yaml")
SHOTS = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "calibration")

WDA = os.environ.get("WDA_URL", "http://169.254.140.1:8100")
SID_FILE = os.environ.get("WDA_SID_FILE", "/tmp/wda_sid.txt")


def _load_raw():
    import yaml
    with open(CONFIG) as f:
        return yaml.safe_load(f)


def _sid() -> str:
    try:
        with open(SID_FILE) as f:
            return f.read().strip()
    except FileNotFoundError:
        sys.exit(
            f"Pas de session WDA dans {SID_FILE}.\n"
            "Démarre WebDriverAgent, puis écris l'identifiant de session dedans."
        )


def _req(method: str, path: str, data=None):
    url = f"{WDA}{path}"
    if data is None:
        request = urllib.request.Request(url, method=method)
    else:
        request = urllib.request.Request(
            url, json.dumps(data).encode(), {"Content-Type": "application/json"}, method=method
        )
    return json.loads(urllib.request.urlopen(request, timeout=15).read())


def _screenshot(name: str) -> str:
    os.makedirs(SHOTS, exist_ok=True)
    payload = _req("GET", f"/session/{_sid()}/screenshot")
    path = os.path.join(SHOTS, f"{name}.png")
    with open(path, "wb") as f:
        f.write(base64.b64decode(payload["value"]))
    return path


def _tap(x: int, y: int) -> None:
    _req("POST", f"/session/{_sid()}/actions", {"actions": [{
        "type": "pointer", "id": "finger", "parameters": {"pointerType": "touch"},
        "actions": [
            {"type": "pointerMove", "duration": 0, "x": x, "y": y},
            {"type": "pointerDown", "button": 0},
            {"type": "pointerUp", "button": 0},
        ],
    }]})


# ------------------------------------------------------------------ commandes

def cmd_list() -> None:
    raw = _load_raw()
    width, height = raw["screen"]["width"], raw["screen"]["height"]
    print(f"écran {width}x{height} points\n")
    for name, point in raw["points"].items():
        mark = "ok " if point.get("calibrated") else "?? "
        px = int(width * point["x"]), int(height * point["y"])
        print(f"  {mark} {name:20} {point['x']:.3f}, {point['y']:.3f}   → {px[0]},{px[1]}")
    missing = [n for n, p in raw["points"].items() if not p.get("calibrated")]
    if missing:
        print(f"\n{len(missing)} point(s) à vérifier : {', '.join(missing)}")


def cmd_shot(name: str = "screen") -> None:
    print(_screenshot(name))


def cmd_probe(name: str) -> None:
    raw = _load_raw()
    point = raw["points"].get(name)
    if point is None:
        sys.exit(f"point inconnu : {name}")
    x = int(raw["screen"]["width"] * point["x"])
    y = int(raw["screen"]["height"] * point["y"])

    before = _screenshot(f"{name}-avant")
    print(f"avant : {before}")
    print(f"tap sur {name} en {x},{y}")
    _tap(x, y)
    time.sleep(1.5)
    after = _screenshot(f"{name}-apres")
    print(f"après : {after}")
    print("\nOuvre les deux images. Si le tap a atterri au bon endroit :")
    print(f"  python -m scripts.calibrate set {name} {point['x']} {point['y']}")


def cmd_set(name: str, x_pct: str, y_pct: str) -> None:
    x, y = float(x_pct), float(y_pct)
    if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
        sys.exit("les coordonnées sont des pourcentages entre 0 et 1")

    # Réécriture ligne à ligne : `yaml.dump` perdrait les commentaires, qui
    # portent l'essentiel de ce qu'on sait de chaque point.
    with open(CONFIG) as f:
        lines = f.readlines()

    needle = f"  {name}:"
    for i, line in enumerate(lines):
        if line.startswith(needle):
            pad = len(needle) - len(f"  {name}:")
            lines[i] = f"  {name}:{' ' * max(1, 21 - len(name) - pad)}{{x: {x}, y: {y}, calibrated: true}}\n"
            break
    else:
        sys.exit(f"point absent de coords.yaml : {name}")

    with open(CONFIG, "w") as f:
        f.writelines(lines)
    print(f"{name} → {x}, {y} (calibré)")


def cmd_pixel(px: str, py: str) -> None:
    raw = _load_raw()
    width, height = raw["screen"]["width"], raw["screen"]["height"]
    x, y = int(px), int(py)
    # Les captures WDA sont en pixels rétine 3x sur iPhone XS ; on accepte les
    # deux échelles et on le signale.
    print(f"si {x},{y} est en points   → x: {x / width:.3f}, y: {y / height:.3f}")
    print(f"si {x},{y} est en pixels 3x → x: {x / (width * 3):.3f}, y: {y / (height * 3):.3f}")


def main() -> None:
    if len(sys.argv) < 2:
        print(__doc__)
        return
    command, args = sys.argv[1], sys.argv[2:]
    handlers = {
        "list": cmd_list, "shot": cmd_shot, "probe": cmd_probe,
        "set": cmd_set, "pixel": cmd_pixel,
    }
    handler = handlers.get(command)
    if handler is None:
        sys.exit(f"commande inconnue : {command}\n\n{__doc__}")
    handler(*args)


if __name__ == "__main__":
    main()
