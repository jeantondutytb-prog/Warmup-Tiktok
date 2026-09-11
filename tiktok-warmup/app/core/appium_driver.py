import json
import os
import subprocess
import tempfile
import time
import urllib.request
import urllib.error

TEAM_ID = "U284BGAVKL"
WDA_BUNDLE_ID = "com.jean.wda.runner"
DERIVED_DATA = "/Users/jean/Library/Developer/Xcode/DerivedData/WebDriverAgent-entqkdybqjzegiahlgkxvxghpzdf"

IPHONE_XS_WIDTH = 375
IPHONE_XS_HEIGHT = 812


class WDADriver:
    """Direct WDA HTTP client — bypasses Appium entirely."""

    def __init__(self, wda_url: str, session_id: str):
        self.wda_url = wda_url.rstrip("/")
        self.session_id = session_id

    def _req(self, method, path, data=None, timeout=15):
        url = f"{self.wda_url}{path}"
        if data is not None:
            req = urllib.request.Request(
                url, data=json.dumps(data).encode(),
                headers={"Content-Type": "application/json"}, method=method,
            )
        else:
            req = urllib.request.Request(url, method=method)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read())
        except (urllib.error.URLError, TimeoutError, OSError):
            raise ConnectionError("WDA not responding")

    def get_window_size(self):
        r = self._req("GET", f"/session/{self.session_id}/window/size")
        return r.get("value", {})

    def get_screenshot_as_base64(self):
        r = self._req("GET", f"/session/{self.session_id}/screenshot", timeout=10)
        return r.get("value", "")

    def activate_app(self, bundle_id):
        self._req("POST", f"/session/{self.session_id}/wda/apps/launch",
                  {"bundleId": bundle_id})

    def terminate_app(self, bundle_id):
        self._req("POST", f"/session/{self.session_id}/wda/apps/terminate",
                  {"bundleId": bundle_id})

    def execute_script(self, script, args=None):
        if script == "mobile: swipe":
            p = args if isinstance(args, dict) else (args[0] if args else {})
            direction = p.get("direction", "up")
            velocity = p.get("velocity", 1500)
            if direction == "up":
                fx, fy, tx, ty = 187, 650, 187, 200
            elif direction == "down":
                fx, fy, tx, ty = 187, 200, 187, 650
            elif direction == "left":
                fx, fy, tx, ty = 300, 406, 75, 406
            else:
                fx, fy, tx, ty = 75, 406, 300, 406
            move_ms = max(150, int(800000 / velocity))
            self._req("POST", f"/session/{self.session_id}/actions", {
                "actions": [{
                    "type": "pointer", "id": "finger1",
                    "parameters": {"pointerType": "touch"},
                    "actions": [
                        {"type": "pointerMove", "duration": 0, "x": fx, "y": fy},
                        {"type": "pointerDown", "button": 0},
                        {"type": "pointerMove", "duration": move_ms, "x": tx, "y": ty, "origin": "viewport"},
                        {"type": "pointerUp", "button": 0},
                    ],
                }],
            })

        elif script == "mobile: tap":
            p = args if isinstance(args, dict) else (args[0] if args else {})
            x, y = p.get("x", 187), p.get("y", 406)
            self._req("POST", f"/session/{self.session_id}/actions", {
                "actions": [{
                    "type": "pointer", "id": "finger1",
                    "parameters": {"pointerType": "touch"},
                    "actions": [
                        {"type": "pointerMove", "duration": 0, "x": x, "y": y},
                        {"type": "pointerDown", "button": 0},
                        {"type": "pointerUp", "button": 0},
                    ],
                }],
            })

        elif script == "mobile: doubleTap":
            p = args if isinstance(args, dict) else (args[0] if args else {})
            x, y = p.get("x", 187), p.get("y", 406)
            self._req("POST", f"/session/{self.session_id}/actions", {
                "actions": [{
                    "type": "pointer", "id": "finger1",
                    "parameters": {"pointerType": "touch"},
                    "actions": [
                        {"type": "pointerMove", "duration": 0, "x": x, "y": y},
                        {"type": "pointerDown", "button": 0},
                        {"type": "pointerUp", "button": 0},
                        {"type": "pause", "duration": 60},
                        {"type": "pointerDown", "button": 0},
                        {"type": "pointerUp", "button": 0},
                    ],
                }],
            })

        elif script == "mobile: pressButton":
            p = args if isinstance(args, dict) else (args[0] if args else {})
            name = p.get("name", "home")
            self._req("POST", f"/session/{self.session_id}/wda/pressButton",
                      {"name": name})

    def find_element(self, using, value):
        wda_using = using
        if using == "ios class chain":
            wda_using = "class chain"
        elif using == "ios predicate string":
            wda_using = "predicate string"
        r = self._req("POST", f"/session/{self.session_id}/element",
                      {"using": wda_using, "value": value}, timeout=10)
        eid = r.get("value", {}).get("ELEMENT") or r.get("value", {}).get("element-6066-11e4-a52e-4f735466cecf")
        return WDAElement(self, eid)

    def double_tap(self, x: int, y: int):
        """Double-tap à (x, y), les deux taps dans une seule chaîne W3C.

        Envoyer deux requêtes HTTP séparées laisserait passer trop de temps
        entre les taps pour que TikTok les lise comme un double-tap. La pause
        est donc décrite dans la chaîne et exécutée sur l'appareil.
        """
        touch = lambda: [
            {"type": "pointerMove", "duration": 0, "x": x, "y": y},
            {"type": "pointerDown", "button": 0},
            {"type": "pause", "duration": 40},
            {"type": "pointerUp", "button": 0},
        ]
        return self._req("POST", f"/session/{self.session_id}/actions", {"actions": [{
            "type": "pointer", "id": "finger", "parameters": {"pointerType": "touch"},
            "actions": touch() + [{"type": "pause", "duration": 90}] + touch(),
        }]})

    def type_text(self, text: str):
        """Tape du texte dans l'élément actuellement focalisé.

        Passe par /wda/keys plutôt que par un élément trouvé : TikTok n'expose
        pas son champ de recherche dans l'arbre d'accessibilité, donc
        find_element échoue ou se bloque. La vue recherche focalise son champ
        toute seule à l'ouverture, ce qui rend le détour inutile.
        """
        return self._req("POST", f"/session/{self.session_id}/wda/keys",
                         {"value": list(text)})

    def back(self):
        self.execute_script("mobile: pressButton", {"name": "home"})
        time.sleep(0.5)
        self.activate_app("com.zhiliaoapp.musically")

    def quit(self):
        try:
            self._req("DELETE", f"/session/{self.session_id}")
        except Exception:
            pass


class WDAElement:
    def __init__(self, driver: WDADriver, element_id: str):
        self.driver = driver
        self.id = element_id

    def send_keys(self, text):
        self.driver._req("POST",
                         f"/session/{self.driver.session_id}/element/{self.id}/value",
                         {"text": text, "value": list(text)})

    def click(self):
        self.driver._req("POST",
                         f"/session/{self.driver.session_id}/element/{self.id}/click")


class AppiumDriverManager:
    def __init__(self, appium_url: str = "http://localhost:4723"):
        # WDA annonce son adresse au démarrage (ligne « ServerURLHere-> » du
        # log xcodebuild). Elle change selon que l'iPhone est joint par le lien
        # USB ou par le Wi-Fi, d'où la surcharge par variable d'environnement.
        self.wda_url = os.environ.get("WDA_URL", "http://169.254.140.1:8100")

    def _get_iphone_udid(self) -> str | None:
        with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
            tmp_path = f.name
        subprocess.run(
            ["xcrun", "devicectl", "list", "devices", "--json-output", tmp_path],
            capture_output=True, text=True,
        )
        try:
            with open(tmp_path) as f:
                data = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            return None
        for device in data.get("result", {}).get("devices", []):
            hw = device.get("hardwareProperties", {})
            conn = device.get("connectionProperties", {})
            props = device.get("deviceProperties", {})
            if (hw.get("deviceType") == "iPhone"
                    and conn.get("pairingState") == "paired"
                    and props.get("bootState") == "booted"):
                return hw.get("udid")
        return None

    def _ensure_wda_running(self):
        try:
            req = urllib.request.Request(f"{self.wda_url}/status")
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read())
                if data.get("value", {}).get("ready"):
                    return True
        except Exception:
            pass

        udid = self._get_iphone_udid()
        if not udid:
            raise RuntimeError("iPhone not detected")

        proc = subprocess.Popen(
            ["xcodebuild", "test-without-building",
             "-project", "/Users/jean/.appium/node_modules/appium-xcuitest-driver/node_modules/appium-webdriveragent/WebDriverAgent.xcodeproj",
             "-scheme", "WebDriverAgentRunner",
             "-derivedDataPath", DERIVED_DATA,
             "-destination", f"id={udid}",
             f"IPHONEOS_DEPLOYMENT_TARGET=18.7",
             f"DEVELOPMENT_TEAM={TEAM_ID}",
             "CODE_SIGN_IDENTITY=Apple Development",
             f"PRODUCT_BUNDLE_IDENTIFIER={WDA_BUNDLE_ID}",
             "GCC_TREAT_WARNINGS_AS_ERRORS=0",
             "COMPILER_INDEX_STORE_ENABLE=NO"],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        )
        for _ in range(60):
            try:
                req = urllib.request.Request(f"{self.wda_url}/status")
                with urllib.request.urlopen(req, timeout=2) as resp:
                    data = json.loads(resp.read())
                    if data.get("value", {}).get("ready"):
                        return True
            except Exception:
                pass
            time.sleep(2)
        raise RuntimeError("WDA failed to start within 120s")

    def create_session(self, device_profile: dict, account_name: str) -> WDADriver:
        self._ensure_wda_running()

        req = urllib.request.Request(
            f"{self.wda_url}/session",
            data=json.dumps({
                "capabilities": {
                    "alwaysMatch": {
                        "bundleId": "com.apple.Preferences",
                        "shouldWaitForQuiescence": False,
                    },
                },
            }).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=30) as resp:
            data = json.loads(resp.read())

        sid = data.get("value", {}).get("sessionId")
        if not sid:
            raise RuntimeError(f"WDA session creation failed: {data}")

        driver = WDADriver(self.wda_url, sid)

        settings_req = urllib.request.Request(
            f"{self.wda_url}/session/{sid}/appium/settings",
            data=json.dumps({"settings": {
                "snapshotMaxDepth": 10,
                "customSnapshotTimeout": 5,
                "animationCoolOffTimeout": 0,
                "snapshotTimeout": 5,
            }}).encode(),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        urllib.request.urlopen(settings_req, timeout=10)

        size = driver.get_window_size()
        if not size or not size.get("width"):
            driver.quit()
            raise RuntimeError("WDA health check failed")

        driver.activate_app("com.zhiliaoapp.musically")
        time.sleep(2)
        return driver

    def close_session(self, driver: WDADriver) -> None:
        driver.quit()
