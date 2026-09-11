import asyncio
import base64
import io
import os
import random
from app.core.appium_driver import WDADriver
from PIL import Image
from app.core.anti_detect import human_delay, should_micro_pause, watch_duration, pick_comment
from app.core.coords import CoordMap, UncalibratedPoint
from app.core import protocol

W, H = 375, 812

TIKTOK_BUNDLE_ID = "com.zhiliaoapp.musically"

# Hauteur minimale, en points, d'une tache rouge pour être un cœur liké et non
# le + d'abonnement. Mesuré sur les captures : cœur 20 pt, + 7 pt.
HEART_MIN_HEIGHT = 12

# Aucune coordonnée en dur ici : config/coords.yaml fait foi. Les constantes
# qui vivaient à cet endroit dataient d'août et pointaient 140 points trop
# haut ; elles ont fait taper 9 likes dans le vide lors de la session #42.


class ActionEngine:
    def __init__(
        self,
        driver: WDADriver,
        comments: dict[str, list[str]],
        comment_style: str,
        coords: CoordMap | None = None,
        trace_dir: str | None = None,
    ):
        self.driver = driver
        self.comments = comments
        self.comment_style = comment_style
        self.coords = coords
        # Quand il est défini, chaque tap laisse une capture datée. Sans ça on
        # ne sait pas sur quel écran une session s'est perdue : les logs
        # d'action décrivent ce que le code a tenté, pas ce qu'il a touché.
        self.trace_dir = trace_dir
        self._trace_n = 0
        self.used_comments_today: set[str] = set()

    async def _snapshot(self, label: str) -> None:
        if not self.trace_dir:
            return
        try:
            os.makedirs(self.trace_dir, exist_ok=True)
            self._trace_n += 1
            b64 = await asyncio.to_thread(self.driver.get_screenshot_as_base64)
            img = Image.open(io.BytesIO(base64.b64decode(b64)))
            img.resize((img.width // 3, img.height // 3)).save(
                os.path.join(self.trace_dir, f"{self._trace_n:03d}-{label}.png")
            )
        except Exception:
            pass

    # ---------------------------------------------------------------- gestes

    async def _tap(self, x: int, y: int) -> None:
        await asyncio.to_thread(
            self.driver.execute_script, "mobile: tap", {"x": x, "y": y}
        )

    async def _tap_point(self, name: str) -> None:
        """Tape un repère nommé de coords.yaml. Lève si le point n'est pas calibré."""
        if self.coords is None:
            raise UncalibratedPoint(
                f"aucune carte de coordonnées chargée, « {name} » est intapable"
            )
        x, y = self.coords.px(name)
        await self._tap(x, y)
        await asyncio.sleep(0.8)
        await self._snapshot(f"tap-{name}")

    async def go_back(self) -> None:
        """Retour arrière par balayage depuis le bord gauche."""
        if self.coords is None:
            return
        fx, fy, tx, ty, ms = self.coords.back_swipe_px()
        await asyncio.to_thread(
            self.driver.execute_script, "mobile: dragFromToForDuration",
            {"fromX": fx, "fromY": fy, "toX": tx, "toY": ty, "duration": ms / 1000},
        )
        await asyncio.sleep(human_delay(0.6, 1.2))

    async def _is_ad_or_live(self) -> str | None:
        try:
            b64 = await asyncio.to_thread(self.driver.get_screenshot_as_base64)
            img = Image.open(io.BytesIO(base64.b64decode(b64)))
            # Lives have a red "LIVE" badge in the top-left area
            # Check a region around (50-120, 60-90) for bright red pixels
            region = img.crop((100, 120, 300, 200))
            pixels = list(region.getdata())
            red_count = sum(1 for r, g, b, *_ in pixels if r > 200 and g < 80 and b < 80)
            red_ratio = red_count / len(pixels) if pixels else 0
            if red_ratio > 0.02:
                return "live"
        except Exception:
            pass
        return None

    async def _escape_live(self) -> None:
        """Press back/close to exit a Live and return to the feed."""
        # Tap the X / close button (top-left on Lives)
        await asyncio.to_thread(
            self.driver.execute_script, "mobile: tap",
            {"x": 20, "y": 60}
        )
        await asyncio.sleep(1.0)
        # If still stuck, swipe down to dismiss
        await asyncio.to_thread(
            self.driver.execute_script, "mobile: swipe",
            {"direction": "down", "velocity": 1500}
        )
        await asyncio.sleep(0.5)

    async def _take_screenshot_hash(self) -> int:
        """Quick perceptual hash of current screen to detect stuck state."""
        try:
            b64 = await asyncio.to_thread(self.driver.get_screenshot_as_base64)
            img = Image.open(io.BytesIO(base64.b64decode(b64)))
            small = img.resize((8, 8)).convert("L")
            return hash(small.tobytes())
        except Exception:
            return 0

    async def scroll_feed(self) -> str:
        """Fait défiler le fil d'une vidéo, et vérifie que ça a bougé.

        Le geste part d'un point tiré dans une zone sûre plutôt que de laisser
        `mobile: swipe` choisir : ses points par défaut peuvent tomber sur la
        légende, la colonne d'actions ou la barre du bas, qui absorbent le
        glissement. Sur la session #46, le fil est resté bloqué sur un post
        `#republication` pendant huit captures consécutives, toutes comptées
        comme des vidéos différentes.

        Renvoie SKIP si le fil refuse d'avancer après trois tentatives, au
        lieu de prétendre avoir scrollé.
        """
        before = await self._take_screenshot_hash()

        for attempt in range(3):
            # Zone sûre : à gauche de la colonne d'actions (x < 320), sous la
            # barre d'onglets et au-dessus de la légende.
            x = random.randint(120, 240)
            duration = 0.28 if attempt == 0 else 0.16
            travel = 380 if attempt == 0 else 520
            await asyncio.to_thread(
                self.driver.execute_script, "mobile: dragFromToForDuration",
                {"fromX": x, "fromY": 600, "toX": x + random.randint(-12, 12),
                 "toY": 600 - travel, "duration": duration},
            )
            await asyncio.sleep(human_delay(0.5, 1.1))

            after = await self._take_screenshot_hash()
            if before == 0 or after != before:
                pause = should_micro_pause(0.05)
                if pause > 0:
                    await asyncio.sleep(pause)
                return "scrolled feed" if attempt == 0 else f"scrolled feed ({attempt + 1}e essai)"

        await self._snapshot("fil-bloque")
        return "SKIP — le fil ne défile plus après trois tentatives"

    async def watch_video(self) -> str:
        duration = watch_duration(30)
        await asyncio.sleep(duration)
        return f"watched {duration}s"

    async def like_video(self) -> str:
        """Like par double-tap au centre, et vérifie que le cœur a changé.

        On ne vise plus le cœur : sa hauteur dépend du type de post et de la
        longueur de la légende. Sur un carrousel photo à longue légende il
        remonte à y≈390 alors que `btn_like` pointe 419 — c'est ce décalage
        qui a fait rater tous les likes de la session #43.

        Le double-tap au centre est le geste universel de TikTok, indépendant
        de la géométrie de la barre latérale. Il ne peut qu'ajouter un like,
        jamais en retirer un, ce qui écarte aussi le risque de dé-liker.
        """
        before = await self._heart_is_red()

        # Une reprise, pas plus : un geste lancé pendant le chargement de la
        # vidéo peut se perdre (observé le 04.09).
        for attempt in range(2):
            try:
                cx, cy = self.coords.px("screen_center") if self.coords else (W // 2, H // 2)
                await asyncio.to_thread(self.driver.double_tap, cx, cy)
            except Exception:
                return "SKIP"
            await asyncio.sleep(human_delay(0.8, 1.5))
            after = await self._heart_is_red()

            if after is None:
                return "liked video (non vérifié)"
            if after:
                if before:
                    return "liked video (déjà liké)"
                return "liked video" if attempt == 0 else "liked video (2e essai)"
            await asyncio.sleep(human_delay(0.8, 1.6))

        await self._snapshot("like-manque")
        return "SKIP — le cœur n'a pas changé après deux taps"

    async def _heart_is_red(self) -> bool | None:
        """Vrai si un cœur liké (rouge) est présent dans la colonne d'actions.

        On balaie toute la colonne au lieu de lire un point : la barre
        latérale glisse verticalement selon le post. Le + d'abonnement est
        rouge lui aussi, d'où la mesure par **hauteur** de la tache — le cœur
        fait une vingtaine de points de haut, le + moins de dix. Mesuré sur
        les captures de calibration : 20 pt liké contre 7 pt non liké.
        """
        try:
            b64 = await asyncio.to_thread(self.driver.get_screenshot_as_base64)
            img = Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB")
            scale = img.width / W
            col = img.crop((int(328 * scale), int(170 * scale),
                            int(362 * scale), int(700 * scale)))
            w, h = col.size
            px = col.load()
            best = run = 0
            for y in range(h):
                red = 0
                for x in range(w):
                    r, g, b = px[x, y]
                    if r > 170 and r - g > 80 and r - b > 80:
                        red += 1
                if red / w > 0.45:
                    run += 1
                    best = max(best, run)
                else:
                    run = 0
            return best / scale > HEART_MIN_HEIGHT
        except Exception:
            return None

    async def follow_user(self) -> str:
        try:
            await self._tap_point("btn_follow")
            await asyncio.sleep(human_delay(0.8, 1.5))
            return "followed user (+ button)"
        except Exception:
            return "SKIP"

    async def comment_on_video(self) -> str:
        comment_text = pick_comment(self.comments, self.comment_style, self.used_comments_today)
        self.used_comments_today.add(comment_text)
        try:
            await asyncio.to_thread(
                self.driver.execute_script, "mobile: tap",
                self.coords.px("btn_comment") and
                {"x": self.coords.px("btn_comment")[0], "y": self.coords.px("btn_comment")[1]}
            )
            await asyncio.sleep(human_delay(1.5, 3.0))

            field = await asyncio.to_thread(
                self.driver.find_element, "ios class chain",
                '**/XCUIElementTypeTextView',
            )
            for char in comment_text:
                await asyncio.to_thread(field.send_keys, char)
                await asyncio.sleep(random.uniform(0.05, 0.15))
            await asyncio.sleep(human_delay(0.5, 1.5))

            send_labels = ["Publier", "Envoyer", "Post", "Send"]
            sent = False
            for label in send_labels:
                try:
                    send_btn = await asyncio.to_thread(
                        self.driver.find_element, "ios predicate string",
                        f'label == "{label}"',
                    )
                    await asyncio.to_thread(send_btn.click)
                    sent = True
                    break
                except Exception:
                    continue

            await asyncio.sleep(human_delay(1.0, 2.0))
            # Close comment panel by tapping above it
            await asyncio.to_thread(
                self.driver.execute_script, "mobile: tap",
                {"x": 187, "y": 100}
            )
            await asyncio.sleep(0.5)

            if sent:
                return f"commented: {comment_text}"
            return "SKIP"
        except Exception:
            try:
                # Close comment panel by tapping above it
                await asyncio.to_thread(
                    self.driver.execute_script, "mobile: tap",
                    {"x": 187, "y": 100}
                )
                await asyncio.sleep(0.5)
            except Exception:
                pass
            return "SKIP"

    async def switch_tiktok_account(self, target_username: str, row_index: int = 0) -> bool:
        try:
            await asyncio.to_thread(
                self.driver.execute_script, "mobile: tap",
                {"x": int(W * 0.90), "y": int(H * 0.97)}
            )
            await asyncio.sleep(human_delay(2.0, 3.5))

            await asyncio.to_thread(
                self.driver.execute_script, "mobile: tap",
                {"x": int(W * 0.40), "y": int(H * 0.16)}
            )
            await asyncio.sleep(human_delay(1.5, 2.5))

            row_y = 0.65 + row_index * 0.085
            await asyncio.to_thread(
                self.driver.execute_script, "mobile: tap",
                {"x": int(W * 0.40), "y": int(H * row_y)}
            )
            await asyncio.sleep(human_delay(2.0, 4.0))

            await asyncio.to_thread(
                self.driver.execute_script, "mobile: tap",
                {"x": int(W * 0.10), "y": int(H * 0.97)}
            )
            await asyncio.sleep(human_delay(1.0, 2.0))
            return True
        except Exception:
            return False


    # ------------------------------------------------------- phase FYP (0-2')

    async def watch_briefly(self) -> str:
        """Regarde une vidéo un court instant, sans replay.

        C'est la façon de traverser un fil dont on ne veut rien renforcer.
        La vue complète et le replay sont les deux signaux les plus forts du
        protocole : les envoyer sur du hors-niche entraîne l'algorithme dans
        la mauvaise direction. Un humain qui tombe sur ce qui ne l'intéresse
        pas scrolle vite — il ne le regarde pas en boucle.
        """
        duration = random.randint(2, 5)
        await asyncio.sleep(duration)
        return f"watched {duration}s (bref, sans replay)"

    async def watch_fully(self) -> str:
        """Regarde une vidéo en entier, puis la laisse boucler si elle est courte.

        Le replay passe devant la vue complète dans l'échelle des signaux du
        protocole : c'est le geste le plus rentable de toute la session.
        """
        duration = watch_duration(30)
        await asyncio.sleep(duration)
        if protocol.should_replay(duration):
            await asyncio.sleep(duration)
            return f"watched {duration}s + replay"
        return f"watched {duration}s"

    # ---------------------------------------------------- phase recherche (2-10')

    async def open_search(self, keyword: str) -> str:
        """Ouvre la recherche et lance un mot-clé unique."""
        await self._tap_point("search_icon")
        await asyncio.sleep(human_delay(1.2, 2.2))

        # Frappe caractère par caractère : un mot-clé collé d'un bloc n'a pas
        # de cadence de frappe. Le champ est déjà focalisé par la vue.
        for char in keyword:
            await asyncio.to_thread(self.driver.type_text, char)
            await asyncio.sleep(random.uniform(0.06, 0.19))
        await asyncio.sleep(human_delay(0.4, 1.1))
        await asyncio.to_thread(self.driver.type_text, "\n")
        await asyncio.sleep(human_delay(2.0, 3.4))
        await self._snapshot("apres-recherche")
        return f"searched: {keyword}"

    async def open_first_result(self) -> str:
        """Ouvre la première vignette de la grille de résultats.

        On ne tape aucun onglet. L'ordre de la rangée « Demander · Top ·
        Vidéos · Utilisateurs · Boutique » **dépend de la requête** : lors de
        la session #42, « Boutique » occupait la position de « Vidéos » et le
        tap a envoyé toute la phase dans TikTok Shop. L'onglet « Top » est
        sélectionné par défaut et contient des vidéos ; c'est aussi ce qu'un
        humain voit en premier.
        """
        await self._tap_point("result_first")
        await asyncio.sleep(human_delay(1.4, 2.4))
        return "opened first result"

    # ----------------------------------------------------- phase profils (10-13')

    async def open_creator_profile(self) -> str:
        await self._tap_point("creator_avatar")
        await asyncio.sleep(human_delay(1.5, 2.6))
        return "opened creator profile"

    async def browse_profile_grid(self) -> str:
        """Scrolle la grille d'un profil puis ouvre une ou deux vidéos.

        On vise le centre de la grille et non « la première cellule » : la
        hauteur de l'en-tête d'un profil varie avec la bio, les stories à la
        une et le panneau de suggestions. Après un défilement, le centre de
        l'écran est une vignette quel que soit le profil.
        """
        await asyncio.to_thread(
            self.driver.execute_script, "mobile: swipe",
            {"direction": "up", "velocity": random.randint(700, 1300)},
        )
        await asyncio.sleep(human_delay(0.8, 1.8))

        opened = random.randint(1, 2)
        for _ in range(opened):
            await self._tap_point("profile_grid_cell")
            await asyncio.sleep(human_delay(1.0, 1.8))
            await asyncio.sleep(watch_duration(20))
            await self.go_back()
            await asyncio.sleep(human_delay(0.8, 1.5))
        return f"browsed grid, opened {opened} video(s)"

    async def follow_from_profile(self) -> str:
        """Tape le bouton « Suivre » d'une page de profil, et le vérifie.

        Distinct de `follow_user`, qui vise le + de la barre latérale d'une
        vidéo : ce bouton-là n'existe pas sur une page de profil.

        La lecture préalable n'est pas un luxe. Sur un profil déjà suivi, le
        bouton devient « Message » **à la même position** : taper sans regarder
        ouvrirait une conversation privée avec un inconnu.
        """
        before = await self._follow_button_is_red()
        if before is False:
            return "SKIP — pas de bouton d'abonnement ici (déjà suivi, ou pas un profil)"

        try:
            await self._tap_point("btn_follow_profile")
        except UncalibratedPoint:
            raise
        except Exception:
            return "SKIP"
        await asyncio.sleep(human_delay(0.9, 1.7))

        after = await self._follow_button_is_red()
        if before is None or after is None:
            return "followed from profile (non vérifié)"
        if after:
            return "SKIP — le bouton est resté « Suivre », tap manqué"
        return "followed from profile"

    async def _follow_button_is_red(self) -> bool | None:
        """Vrai si une pastille d'abonnement rouge occupe `btn_follow_profile`.

        « Suivre » et « Suivre en retour » sont de larges pastilles rouges ;
        une fois abonné, le bouton devient « Message », gris. Mesuré sur les
        captures de calibration : 89-95 % de rouge avant, 0 % après.
        """
        if self.coords is None:
            return None
        try:
            x, y = self.coords.px("btn_follow_profile")
            b64 = await asyncio.to_thread(self.driver.get_screenshot_as_base64)
            img = Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB")
            scale = img.width / self.coords.width
            bw, bh = int(70 * scale), int(12 * scale)
            cx, cy = int(x * scale), int(y * scale)
            box = img.crop((cx - bw, cy - bh, cx + bw, cy + bh))
            pixels = list(box.getdata())
            red = sum(1 for r, g, b in pixels if r > 170 and r - g > 70 and r - b > 60)
            return red / len(pixels) > 0.55
        except Exception:
            return None

    async def return_to_feed(self) -> str:
        """Ramène l'app sur le fil « Pour toi », depuis n'importe quel écran.

        Taper `home_tab` ne suffit pas : sur une vidéo ouverte depuis la
        recherche ou un profil, la barre du bas n'est pas la barre d'onglets
        mais le champ « Ajouter un commentaire », au même endroit. Le tap
        ouvre alors le clavier et l'app y reste bloquée.

        Relancer l'app est le seul retour déterministe : TikTok rouvre
        toujours sur le fil.
        """
        await asyncio.to_thread(self.driver.terminate_app, TIKTOK_BUNDLE_ID)
        await asyncio.sleep(human_delay(1.0, 2.0))
        await asyncio.to_thread(self.driver.activate_app, TIKTOK_BUNDLE_ID)
        await asyncio.sleep(human_delay(3.0, 5.0))

        await self._snapshot("retour-fil")
        if await self._keyboard_is_up():
            return "SKIP"
        return "back on feed"

    async def _keyboard_is_up(self) -> bool:
        """Vrai si le bas de l'écran ressemble à un clavier.

        Le clavier iOS est une large plage claire ; le fil TikTok a un bas
        quasi noir. Une moyenne de luminosité suffit à les séparer, sans
        dépendre de l'arbre d'accessibilité que TikTok n'expose pas.
        """
        try:
            b64 = await asyncio.to_thread(self.driver.get_screenshot_as_base64)
            img = Image.open(io.BytesIO(base64.b64decode(b64))).convert("L")
            w, h = img.size
            band = img.crop((0, int(h * 0.72), w, h))
            pixels = list(band.getdata())
            return sum(pixels) / len(pixels) > 110
        except Exception:
            return False

    # ------------------------------------------------- phase mesure (13-18')

    async def measure_fyp(self, shots_dir: str) -> tuple[int, int]:
        """Scrolle le FYP et capture chaque vidéo pour comptage.

        Renvoie (captures prises, vidéos distinctes). La distinction compte :
        sur la session #46 les 20 captures ne contenaient que 9 vidéos, le fil
        étant resté bloqué. Compter 20 aurait donné une mesure fausse.

        Le comptage des vidéos « de la niche » reste manuel : le reconnaître
        sur une capture n'est pas fiable sans OCR, et aucun n'est installé.
        """
        os.makedirs(shots_dir, exist_ok=True)
        taken = 0
        hashes: list[int] = []
        for i in range(protocol.FYP_MEASURE_SCROLLS):
            try:
                b64 = await asyncio.to_thread(self.driver.get_screenshot_as_base64)
                img = Image.open(io.BytesIO(base64.b64decode(b64)))
                img.save(os.path.join(shots_dir, f"{i:02d}.png"))
                hashes.append(await self._take_screenshot_hash())
                taken += 1
            except Exception:
                pass
            await asyncio.sleep(human_delay(1.5, 3.5))
            if (await self.scroll_feed()).startswith("SKIP"):
                break
        distinct = len({h for h in hashes if h})
        return taken, distinct

    async def execute_action(self, action_type: str) -> str:
        dispatch = {
            "scroll": self.scroll_feed,
            "watch": self.watch_video,
            "like": self.like_video,
            "follow": self.follow_user,
            "comment": self.comment_on_video,
            "watch_fully": self.watch_fully,
            "watch_briefly": self.watch_briefly,
            "visit_profile": self.open_creator_profile,
            "follow_profile": self.follow_from_profile,
            "return_to_feed": self.return_to_feed,
        }
        handler = dispatch.get(action_type)
        if handler is None:
            raise ValueError(f"Unknown action type: {action_type}")
        return await handler()
