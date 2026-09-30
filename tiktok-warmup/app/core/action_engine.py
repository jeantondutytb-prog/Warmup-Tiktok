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

# Le + d'abonnement sous l'avatar du créateur : 22 pt de côté, et l'avatar
# centré 28 pt au-dessus de son centre. Mesuré le 30.09.2026 sur iPhone XS.
BADGE_MIN_PT, BADGE_MAX_PT = 16, 25
AVATAR_ABOVE_BADGE = 28

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
        self._profile_texts: list[tuple[str, int, int]] = []

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
            w, h = img.size

            live_zone = img.crop((int(w * 0.02), int(h * 0.04),
                                  int(w * 0.55), int(h * 0.15)))
            live_px = list(live_zone.getdata())
            red = sum(1 for r, g, b, *_ in live_px
                      if r > 200 and g < 80 and b < 80)
            if live_px and red / len(live_px) > 0.012:
                return "live"

            ad_zone = img.crop((int(w * 0.10), int(h * 0.82),
                                int(w * 0.90), int(h * 0.90)))
            ad_px = list(ad_zone.getdata())
            blue = sum(1 for r, g, b, *_ in ad_px
                       if b > 170 and b - r > 40 and b - g > 25)
            if ad_px and blue / len(ad_px) > 0.08:
                return "ad"

            return None
        except Exception:
            return None

    async def _escape_live(self) -> None:
        """Ferme un live et retourne au fil. Tap X puis balayage arrière."""
        await self._tap(int(W * 0.06), int(H * 0.065))
        await asyncio.sleep(1.0)
        await asyncio.to_thread(
            self.driver.execute_script, "mobile: dragFromToForDuration",
            {"fromX": 5, "fromY": H // 2, "toX": int(W * 0.6),
             "toY": H // 2, "duration": 0.2},
        )
        await asyncio.sleep(0.8)

    async def _take_screenshot_hash(self) -> int:
        """Hash de la colonne d'actions + légende pour détecter un changement de vidéo.

        Le hash de l'écran entier changeait à chaque frame de la vidéo, rendant
        la détection de scroll inutile (toujours « changé »). La bande droite
        (avatar, cœur, commentaire, partage) et la bande basse (pseudo, légende)
        ne changent qu'au passage à une autre vidéo.
        """
        try:
            b64 = await asyncio.to_thread(self.driver.get_screenshot_as_base64)
            img = Image.open(io.BytesIO(base64.b64decode(b64)))
            w, h = img.size
            sidebar = img.crop((int(w * 0.82), int(h * 0.25), w, int(h * 0.85)))
            bottom = img.crop((0, int(h * 0.85), int(w * 0.75), h))
            sidebar_small = sidebar.resize((6, 12)).convert("L")
            bottom_small = bottom.resize((12, 4)).convert("L")
            return hash(sidebar_small.tobytes() + bottom_small.tobytes())
        except Exception:
            return 0

    async def scroll_feed(self) -> str:
        """Fait défiler le fil d'une vidéo, en sautant les lives et pubs.

        Après chaque scroll réussi, vérifie si la nouvelle vidéo est un live
        ou une pub. Un live bloque le geste de scroll (les commentaires
        captent le geste) ; une pub gaspille le budget de visionnage. Dans
        les deux cas, on saute et on re-scrolle jusqu'à un contenu normal.
        """
        skipped = []
        # Tentative qui a fait bouger le dernier geste : un fil qui ne cède
        # qu'au 2e ou 3e essai se lit dans les logs, pas seulement un blocage.
        attempt = 0

        for _ in range(6):
            before = await self._take_screenshot_hash()
            scrolled = False

            for attempt in range(3):
                x = random.randint(120, 240)
                dur = 0.28 if attempt == 0 else 0.16
                travel = 380 if attempt == 0 else 520
                await asyncio.to_thread(
                    self.driver.execute_script, "mobile: dragFromToForDuration",
                    {"fromX": x, "fromY": 600, "toX": x + random.randint(-12, 12),
                     "toY": 600 - travel, "duration": dur},
                )
                await asyncio.sleep(human_delay(0.5, 1.1))

                after = await self._take_screenshot_hash()
                if before == 0 or after != before:
                    scrolled = True
                    break

            if not scrolled:
                content_type = await self._is_ad_or_live()
                if content_type == "live":
                    await self._escape_live()
                    skipped.append("live")
                    continue
                await self._snapshot("fil-bloque")
                return "SKIP — le fil ne défile plus après trois tentatives"

            content_type = await self._is_ad_or_live()
            if content_type is None:
                break

            skipped.append(content_type)
            await self._snapshot(f"skip-{content_type}")
            if content_type == "live":
                await self._escape_live()

        pause = should_micro_pause(0.05)
        if pause > 0:
            await asyncio.sleep(pause)

        notes = []
        if attempt:
            notes.append(f"{attempt + 1}e essai")
        if skipped:
            notes.append(f"sauté {len(skipped)} {'/'.join(skipped)}")
        return f"scrolled feed ({', '.join(notes)})" if notes else "scrolled feed"

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
        return "SKIP — cœur toujours blanc après deux taps"

    async def _heart_is_red(self) -> bool | None:
        """Vrai si un cœur liké (rouge) est présent dans la colonne d'actions."""
        try:
            b64 = await asyncio.to_thread(self.driver.get_screenshot_as_base64)
            img = Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB")
            w, h = img.size
            col = img.crop((int(w * 0.84), int(h * 0.20),
                            int(w * 0.99), int(h * 0.78)))
            cw, ch = col.size
            px = col.load()
            best = run = 0
            for y in range(ch):
                red = 0
                for x in range(cw):
                    r, g, b = px[x, y]
                    if r > 170 and r - g > 70 and r - b > 60:
                        red += 1
                if red / cw > 0.25:
                    run += 1
                    best = max(best, run)
                else:
                    run = 0
            scale = w / W
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
        """Commente depuis la barre « Ajouter un commentaire… », lue à l'écran.

        TikTok n'expose pas son champ dans l'arbre d'accessibilité : l'ancienne
        version le cherchait par XCUITest et échouait à tous les coups. La
        barre n'existe que sous une vidéo ouverte depuis une recherche, ce qui
        tombe bien : c'est là que sont les vidéos de la niche.
        """
        texts = await self._screen_text()
        lowered = [(t.lower(), x, y) for t, x, y in texts]
        if any("limité l'accès aux commentaires" in t for t, _, _ in lowered):
            return "SKIP — commentaires fermés par le créateur"
        bar = next(((x, y) for t, x, y in lowered if "ajouter un commentaire" in t), None)
        if bar is None:
            return "SKIP — pas de barre de commentaire sur cet écran"

        comment_text = pick_comment(self.comments, self.comment_style, self.used_comments_today)
        await self._tap(*bar)
        await asyncio.sleep(human_delay(1.2, 2.0))
        await asyncio.to_thread(self.driver.type_text, comment_text)
        await asyncio.sleep(human_delay(0.8, 1.6))
        await asyncio.to_thread(self.driver.type_text, "\n")
        await asyncio.sleep(human_delay(1.5, 2.5))
        await self._snapshot("commentaire")

        after = [t.lower() for t, _, _ in await self._screen_text()]
        if any("ajouter un commentaire" in t for t in after):
            self.used_comments_today.add(comment_text)
            return f"commented: {comment_text}"
        return "SKIP — commentaire tapé mais pas envoyé"

    # ------------------------------------------------------- compte actif

    async def _screen_text(self) -> list[tuple[str, int, int]]:
        """Texte lu à l'écran par l'OCR de macOS : (texte, x, y) en points."""
        from ocrmac import ocrmac
        b64 = await asyncio.to_thread(self.driver.get_screenshot_as_base64)
        img = Image.open(io.BytesIO(base64.b64decode(b64)))
        found = await asyncio.to_thread(
            lambda: ocrmac.OCR(img, language_preference=["fr-FR", "en-US"]).recognize()
        )
        # Vision renvoie des boîtes normalisées, origine en bas à gauche.
        return [
            (text, int((x + w / 2) * W), int((1 - (y + h / 2)) * H))
            for text, _conf, (x, y, w, h) in found
        ]

    @staticmethod
    def _norm(text: str) -> str:
        # Un nom TikTok n'a jamais de majuscule : le « I » que l'OCR lit dans
        # « @mateo.ltpr » est toujours un « l ».
        return text.replace("I", "l").replace("|", "l").lower().replace("@", "").replace(" ", "")

    async def current_account(self, known: list[str]) -> str | None:
        """Le compte TikTok ouvert, lu sur la page profil. None si ambigu."""
        await self._tap_point("profile_tab")
        await asyncio.sleep(human_delay(2.0, 3.0))
        self._profile_texts = await self._screen_text()
        texts = [self._norm(t) for t, _, _ in self._profile_texts]
        matches = {u for u in known if any(self._norm(u) == t for t in texts)}
        await self._snapshot("compte-actif")
        return matches.pop() if len(matches) == 1 else None

    async def switch_tiktok_account(self, target: str, known: list[str]) -> str:
        """Bascule sur `target` et le vérifie. Renvoie "" si c'est fait, sinon le motif.

        Aucune session ne doit tourner sur un compte qu'on n'a pas lu à
        l'écran : un tap de travers dans le sélecteur ferait chauffer un
        compte protégé à la place du bon.
        """
        current = await self.current_account(known)
        if current == target:
            return ""

        # Le nom en gros (pas le @pseudo en dessous) ouvre le sélecteur. Sa
        # place change avec la mise en page : centré sous l'avatar à y≈201 le
        # 28.09, en haut à gauche à y≈120 le 30.09 — où l'ancien point tapait
        # le compteur « J'aime ». On le lit donc à l'écran.
        name = None
        if current:
            candidates = [
                (y, x) for t, x, y in self._profile_texts
                if not t.strip().startswith("@") and self._norm(t).startswith(self._norm(current))
            ]
            if candidates:
                y, x = min(candidates)
                name = (x, y)
        if name:
            await self._tap(*name)
            await asyncio.sleep(0.8)
        else:
            await self._tap_point("display_name")
        await asyncio.sleep(human_delay(1.5, 2.5))
        await self._snapshot("selecteur-comptes")

        row = None
        for attempt in range(2):
            for text, x, y in await self._screen_text():
                if self._norm(target) in self._norm(text):
                    row = (x, y)
                    break
            if row or attempt:
                break
            await asyncio.to_thread(
                self.driver.execute_script, "mobile: dragFromToForDuration",
                {"fromX": W // 2, "fromY": int(H * 0.85), "toX": W // 2,
                 "toY": int(H * 0.55), "duration": 0.4},
            )
            await asyncio.sleep(1.0)

        if row is None:
            await self.go_back()
            return f"@{target} absent du sélecteur de comptes de l'app"

        await self._tap(*row)
        await asyncio.sleep(human_delay(5.0, 7.0))

        now = await self.current_account(known)
        if now != target:
            return f"après bascule, compte lu à l'écran : {now or 'illisible'}"
        return ""


    # ------------------------------------------------------- phase FYP (0-2')

    async def watch_briefly(self) -> str:
        """Regarde une vidéo un court instant, sans replay.

        C'est la façon de traverser un fil dont on ne veut rien renforcer.
        La vue complète et le replay sont les deux signaux les plus forts du
        protocole : les envoyer sur du hors-niche entraîne l'algorithme dans
        la mauvaise direction. Un humain qui tombe sur ce qui ne l'intéresse
        pas scrolle vite — il ne le regarde pas en boucle.
        """
        content_type = await self._is_ad_or_live()
        if content_type:
            return f"SKIP — {content_type} détecté"
        duration = random.randint(2, 5)
        await asyncio.sleep(duration)
        return f"watched {duration}s (bref, sans replay)"

    async def watch_fully(self) -> str:
        """Regarde une vidéo en entier, puis la laisse boucler si elle est courte.

        Le replay passe devant la vue complète dans l'échelle des signaux du
        protocole : c'est le geste le plus rentable de toute la session.
        """
        content_type = await self._is_ad_or_live()
        if content_type:
            return f"SKIP — {content_type} détecté"
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

        # Frappe par groupes de 3-5 caractères : un par un est trop lent (6s
        # pour 32 chars) et les suggestions d'autocomplétion de TikTok peuvent
        # avaler des caractères ; un bloc entier n'a pas de cadence humaine.
        i = 0
        while i < len(keyword):
            chunk = random.randint(3, 5)
            text = keyword[i:i + chunk]
            await asyncio.to_thread(self.driver.type_text, text)
            i += len(text)
            if i < len(keyword):
                await asyncio.sleep(random.uniform(0.12, 0.35))
        await asyncio.sleep(human_delay(0.6, 1.2))
        await self._snapshot("avant-rechercher")

        # Le bouton « rechercher » du clavier iOS. type_text("\n") n'envoie
        # qu'un caractère, pas la touche Return — il faut taper le bouton.
        # Mesuré sur capture : centre à x=87.5%, y=87% (iPhone XS).
        await self._tap(int(W * 0.875), int(H * 0.87))
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
        """Tape l'avatar du créateur, repéré par le + rouge qu'il porte, et
        vérifie qu'un profil s'est bien ouvert.

        L'avatar n'a pas de position fixe : sur une vidéo ouverte depuis la
        recherche, la colonne remonte de 36 pt. Le `creator_avatar` calibré sur
        le fil tombait alors pile sur le + : le 30.09 le test rapide a abonné
        margaux.fgts sans ouvrir de profil, tout en journalisant « opened
        creator profile ». D'où les 12 abonnements d'antoine.ckts.
        """
        badge = await self._follow_badge()
        if badge:
            await self._tap(badge[0], badge[1] - AVATAR_ABOVE_BADGE)
            await asyncio.sleep(0.8)
            await self._snapshot("tap-avatar")
        else:
            # Pas de + : créateur déjà suivi, le point du fil ne risque rien.
            await self._tap_point("creator_avatar")
        await asyncio.sleep(human_delay(1.5, 2.6))

        texts = [t.lower() for t, _, _ in await self._screen_text()]
        if any("follower" in t for t in texts) and any("suivi" in t for t in texts):
            return "opened creator profile"
        await self._snapshot("profil-manque")
        return "SKIP — le profil du créateur ne s'est pas ouvert"

    async def _follow_badge(self) -> tuple[int, int] | None:
        """Centre, en points, du + rouge sous l'avatar du créateur. None s'il
        n'y en a pas (créateur déjà suivi, live, pub).

        Mesuré le 30.09 : + de 22×22 pt centré sur x≈345. Le cœur liké, dans la
        même colonne et de la même couleur, fait 27×29 pt : la taille suffit à
        les distinguer.
        """
        try:
            b64 = await asyncio.to_thread(self.driver.get_screenshot_as_base64)
            img = Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB")
            w, h = img.size
            scale = w / W
            x0, x1 = int(w * 0.84), int(w * 0.99)
            px = img.load()

            def red_xs(y: int) -> list[int]:
                out = []
                for x in range(x0, x1):
                    r, g, b = px[x, y]
                    if r > 170 and r - g > 70 and r - b > 60:
                        out.append(x)
                return out

            start = None
            xs: list[int] = []
            for y in range(int(h * 0.25), int(h * 0.65)):
                row = red_xs(y)
                if len(row) >= 3:
                    if start is None:
                        start, xs = y, []
                    xs.extend(row)
                    continue
                if start is not None:
                    bh = (y - start) / scale
                    bw = (max(xs) - min(xs)) / scale
                    if BADGE_MIN_PT <= bh <= BADGE_MAX_PT and BADGE_MIN_PT <= bw <= BADGE_MAX_PT:
                        return (int((min(xs) + max(xs)) / 2 / scale),
                                int((start + y) / 2 / scale))
                    start = None
            return None
        except Exception:
            return None

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
        """Vrai si le bouton « Suivre » rouge est visible, False si « Message »
        gris (déjà suivi), None si incertain (bouton décalé par une bio longue).
        """
        if self.coords is None:
            return None
        try:
            x, y = self.coords.px("btn_follow_profile")
            b64 = await asyncio.to_thread(self.driver.get_screenshot_as_base64)
            img = Image.open(io.BytesIO(base64.b64decode(b64))).convert("RGB")
            scale = img.width / self.coords.width
            bw, bh = int(90 * scale), int(22 * scale)
            cx, cy = int(x * scale), int(y * scale)
            box = img.crop((cx - bw, cy - bh, cx + bw, cy + bh))
            pixels = list(box.getdata())
            red = sum(1 for r, g, b in pixels if r > 170 and r - g > 70 and r - b > 60)
            ratio = red / len(pixels)
            if ratio > 0.30:
                return True
            if ratio < 0.05:
                return False
            return None
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
