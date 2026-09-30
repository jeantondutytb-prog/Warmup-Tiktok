"""ActionEngine pour TikTok web — même interface que l'ActionEngine mobile."""

import asyncio
import os
import random
import sys
from app.core.anti_detect import human_delay, should_micro_pause, watch_duration, pick_comment
from app.core import protocol


class BrowserActionEngine:
    """Pilote TikTok web via Playwright. Substituable à ActionEngine (mobile)."""

    def __init__(self, page, comments, comment_style, trace_dir=None):
        self.page = page
        self.comments = comments
        self.comment_style = comment_style
        self.trace_dir = trace_dir
        self._trace_n = 0
        self.used_comments_today: set[str] = set()

    # ---------------------------------------------------------------- helpers

    async def _snapshot(self, label: str) -> None:
        if not self.trace_dir:
            return
        try:
            os.makedirs(self.trace_dir, exist_ok=True)
            self._trace_n += 1
            path = os.path.join(self.trace_dir, f"{self._trace_n:03d}-{label}.png")
            await self.page.screenshot(path=path)
        except Exception:
            pass

    async def _dismiss_popups(self) -> None:
        """Ferme les bannières cookies et popups non-login de TikTok."""
        try:
            for text in ("Decline optional cookies", "Refuser", "Tout refuser",
                         "Reject all", "Decline all"):
                btn = self.page.locator(f'button:has-text("{text}")')
                if await btn.count() > 0:
                    await btn.first.click(timeout=2000)
                    await asyncio.sleep(0.5)
                    break

            close = self.page.locator(
                '[data-e2e="modal-close-inner-button"]'
            ).or_(
                self.page.locator('button[aria-label="Close"]')
            ).or_(
                self.page.locator('[class*="DivCloseIcon"]')
            )
            if await close.count() > 0:
                await close.first.click(timeout=2000)
                await asyncio.sleep(0.5)
        except Exception:
            pass

    async def _login_modal_visible(self) -> bool:
        """Vrai si la popup « Connecte-toi à TikTok » est affichée."""
        try:
            for text in ("Connecte-toi à TikTok", "Log in to TikTok",
                         "Log in to your account"):
                modal = self.page.locator(f'text="{text}"')
                if await modal.count() > 0:
                    return True
            return False
        except Exception:
            return False

    async def _human_mouse_move(self) -> None:
        try:
            vw = self.page.viewport_size
            if vw:
                x = random.randint(100, vw["width"] - 100)
                y = random.randint(100, vw["height"] - 100)
                await self.page.mouse.move(x, y, steps=random.randint(5, 15))
        except Exception:
            pass

    async def _loc(self, *selectors):
        """Renvoie le premier locator qui matche parmi les sélecteurs."""
        for sel in selectors:
            loc = self.page.locator(sel)
            if await loc.count() > 0:
                return loc.first
        return None

    # ---------------------------------------------------------------- navigation

    async def return_to_feed(self) -> str:
        try:
            await self.page.goto(
                "https://www.tiktok.com/foryou",
                wait_until="domcontentloaded", timeout=15000,
            )
            await asyncio.sleep(human_delay(2.0, 4.0))
            await self._dismiss_popups()

            if "/login" in self.page.url or await self._login_modal_visible():
                return "SKIP — session expirée, reconnexion nécessaire"

            await self._snapshot("retour-fil")
            return "back on feed"
        except Exception as e:
            return f"SKIP — {e}"

    async def go_back(self) -> None:
        try:
            await self.page.go_back(wait_until="domcontentloaded", timeout=10000)
            await asyncio.sleep(human_delay(1.0, 2.0))
        except Exception:
            pass

    # ---------------------------------------------------------------- FYP (0-2′)

    async def watch_briefly(self) -> str:
        duration = random.randint(2, 5)
        await asyncio.sleep(duration)
        await self._human_mouse_move()
        return f"watched {duration}s (bref, sans replay)"

    async def watch_fully(self) -> str:
        duration = watch_duration(30)
        await asyncio.sleep(duration)
        if protocol.should_replay(duration):
            await asyncio.sleep(duration)
            suffix = f"watched {duration}s + replay"
        else:
            suffix = f"watched {duration}s"
        if await self._page_alive():
            return suffix
        return f"SKIP — page morte pendant la lecture ({suffix})"

    async def watch_video(self) -> str:
        duration = watch_duration(30)
        await asyncio.sleep(duration)
        if await self._page_alive():
            return f"watched {duration}s"
        return f"SKIP — page morte pendant la lecture (watched {duration}s)"

    async def _page_alive(self) -> bool:
        try:
            await self.page.evaluate("1")
            return not self.page.is_closed()
        except Exception:
            return False

    async def scroll_feed(self) -> str:
        """Passe à la vidéo suivante dans le fil."""
        for attempt in range(3):
            try:
                if attempt == 0:
                    await self.page.keyboard.press("ArrowDown")
                elif attempt == 1:
                    await self.page.mouse.wheel(0, 600)
                else:
                    await self.page.evaluate("window.scrollBy(0, window.innerHeight)")

                await asyncio.sleep(human_delay(0.8, 1.5))

                pause = should_micro_pause(0.05)
                if pause > 0:
                    await asyncio.sleep(pause)

                await self._snapshot("scroll")
                return "scrolled feed"
            except Exception:
                continue

        return "SKIP — le fil ne défile plus après trois tentatives"

    # ---------------------------------------------------------------- recherche (2-10′)

    async def open_search(self, keyword: str) -> str:
        try:
            encoded = keyword.replace(" ", "+")
            await self.page.goto(
                f"https://www.tiktok.com/search/video?q={encoded}",
                wait_until="domcontentloaded", timeout=20000,
            )
            await asyncio.sleep(human_delay(2.0, 4.0))

            if "/login" in self.page.url or await self._login_modal_visible():
                await self._snapshot("recherche-login-bloque")
                return "SKIP — popup de connexion après la recherche"

            await self._dismiss_popups()

            for tab_text in ("Vidéos", "Videos"):
                tab = self.page.locator(
                    f'[data-e2e="search_top-tab"]:has-text("{tab_text}")'
                )
                if await tab.count() > 0:
                    await tab.first.click()
                    await asyncio.sleep(human_delay(1.0, 2.0))
                    break

            await self._snapshot("apres-recherche")
            return f"searched: {keyword}"
        except Exception as e:
            await self._snapshot("recherche-erreur")
            return f"SKIP — recherche échouée : {e}"

    async def open_first_result(self) -> str:
        try:
            video = await self._loc(
                '[data-e2e="search_top-item"]',
                '[data-e2e="search-card-desc"]',
                '[class*="DivVideoCardContainer"]',
                'a[href*="/video/"]',
            )
            if video:
                await video.click()
                await asyncio.sleep(human_delay(2.0, 3.5))
                await self._dismiss_popups()
                await self._snapshot("premier-resultat")
                return "opened first result"

            return "SKIP — aucun résultat trouvé"
        except Exception as e:
            return f"SKIP — {e}"

    async def like_video(self) -> str:
        try:
            like_btn = await self._loc(
                '[data-e2e="like-icon"]',
                '[data-e2e="browse-like-icon"]',
            )
            if like_btn:
                pressed = await like_btn.get_attribute("aria-pressed")
                if pressed == "true":
                    return "SKIP — déjà liké"
                await like_btn.click()
                await asyncio.sleep(human_delay(0.8, 1.5))
                pressed = await like_btn.get_attribute("aria-pressed")
                if pressed == "true":
                    return "liked video"
                return "liked video (clic envoyé, non confirmé)"

            video = self.page.locator("video")
            if await video.count() > 0:
                box = await video.first.bounding_box()
                if box:
                    x = box["x"] + box["width"] / 2
                    y = box["y"] + box["height"] / 2
                    await self.page.mouse.dblclick(x, y)
                    await asyncio.sleep(human_delay(0.8, 1.5))
                    return "liked video (double-clic)"

            return "SKIP — bouton like introuvable"
        except Exception as e:
            return f"SKIP — {e}"

    # ---------------------------------------------------------------- profils (10-13′)

    async def open_creator_profile(self) -> str:
        try:
            avatar = await self._loc(
                '[data-e2e="browse-user-avatar"]',
                '[data-e2e="video-author-avatar"]',
                '[class*="DivAvatarContainer"] a',
                'a[data-e2e="video-author-uniqueid"]',
            )
            if avatar:
                await avatar.click()
                await asyncio.sleep(human_delay(2.0, 4.0))
                await self._dismiss_popups()
                await self._snapshot("profil-createur")
                return "opened creator profile"

            username_link = self.page.locator('a[href*="/@"]')
            if await username_link.count() > 0:
                await username_link.first.click()
                await asyncio.sleep(human_delay(2.0, 4.0))
                return "opened creator profile (fallback)"

            return "SKIP — avatar/nom du créateur introuvable"
        except Exception as e:
            return f"SKIP — {e}"

    async def browse_profile_grid(self) -> str:
        try:
            await self.page.mouse.wheel(0, random.randint(300, 600))
            await asyncio.sleep(human_delay(1.0, 2.0))

            videos = self.page.locator(
                '[data-e2e="user-post-item"]'
            ).or_(
                self.page.locator('[data-e2e="user-post-item-desc"]')
            ).or_(
                self.page.locator('[class*="DivVideoFeedV2"] a[href*="/video/"]')
            )

            count = await videos.count()
            if count == 0:
                return "SKIP — grille vide"

            opened = 0
            indices = random.sample(range(min(count, 6)), min(random.randint(1, 2), min(count, 6)))
            for idx in indices:
                await videos.nth(idx).click()
                await asyncio.sleep(human_delay(1.5, 2.5))
                await asyncio.sleep(watch_duration(20))
                opened += 1
                await self.go_back()
                await asyncio.sleep(human_delay(0.8, 1.5))

            return f"browsed grid, opened {opened} video(s)"
        except Exception as e:
            return f"SKIP — {e}"

    async def follow_from_profile(self) -> str:
        try:
            for text in ("Following", "Suivi(e)", "Abonné", "Friends", "Amis"):
                already = self.page.locator(f'button:has-text("{text}")')
                if await already.count() > 0:
                    return "SKIP — déjà abonné"

            follow_btn = await self._loc(
                '[data-e2e="follow-button"]',
                'button:has-text("Follow")',
                'button:has-text("Suivre")',
            )
            if follow_btn:
                await follow_btn.click()
                await asyncio.sleep(human_delay(1.0, 2.0))
                return "followed from profile"

            return "SKIP — bouton suivre introuvable"
        except Exception as e:
            return f"SKIP — {e}"

    async def follow_user(self) -> str:
        try:
            follow_btn = await self._loc(
                '[data-e2e="browse-follow"]',
                '[data-e2e="video-follow"]',
            )
            if follow_btn:
                await follow_btn.click()
                await asyncio.sleep(human_delay(0.8, 1.5))
                return "followed user"
            return "SKIP — bouton follow introuvable"
        except Exception as e:
            return f"SKIP — {e}"

    async def comment_on_video(self) -> str:
        comment_text = pick_comment(
            self.comments, self.comment_style, self.used_comments_today
        )
        self.used_comments_today.add(comment_text)
        try:
            comment_btn = await self._loc(
                '[data-e2e="comment-icon"]',
                '[data-e2e="browse-comment-icon"]',
            )
            if comment_btn:
                await comment_btn.click()
                await asyncio.sleep(human_delay(1.5, 3.0))

            comment_input = await self._loc(
                '[data-e2e="comment-input"]',
                '[contenteditable="true"]',
                'div[class*="DivInputEditorContainer"] [contenteditable]',
            )
            if not comment_input:
                return "SKIP — champ de commentaire introuvable"

            await comment_input.click()
            await asyncio.sleep(human_delay(0.3, 0.8))

            for char in comment_text:
                await self.page.keyboard.type(char)
                await asyncio.sleep(random.uniform(0.04, 0.14))

            await asyncio.sleep(human_delay(0.5, 1.5))

            post_btn = await self._loc(
                '[data-e2e="comment-post"]',
                'button:has-text("Post")',
                'button:has-text("Publier")',
            )
            if post_btn:
                await post_btn.click()
            else:
                await self.page.keyboard.press("Enter")

            await asyncio.sleep(human_delay(1.0, 2.0))
            return f"commented: {comment_text}"
        except Exception:
            return "SKIP"

    # ---------------------------------------------------------------- mesure (13-18′)

    async def measure_fyp(self, shots_dir: str) -> tuple[int, int]:
        os.makedirs(shots_dir, exist_ok=True)
        taken = 0
        hashes: list[int] = []

        for i in range(protocol.FYP_MEASURE_SCROLLS):
            try:
                path = os.path.join(shots_dir, f"{i:02d}.png")
                await self.page.screenshot(path=path)
                taken += 1

                h = await self._screenshot_hash()
                hashes.append(h)
            except Exception:
                pass

            await asyncio.sleep(human_delay(1.5, 3.5))
            result = await self.scroll_feed()
            if result.startswith("SKIP"):
                break

        distinct = len({h for h in hashes if h})
        return taken, distinct

    async def _screenshot_hash(self) -> int:
        """Hash de la bande basse de l'écran pour distinguer les vidéos."""
        try:
            from PIL import Image
            import io
            raw = await self.page.screenshot()
            img = Image.open(io.BytesIO(raw))
            w, h = img.size
            bottom = img.crop((0, int(h * 0.75), w, h))
            small = bottom.resize((20, 5)).convert("L")
            return hash(small.tobytes())
        except Exception:
            return 0

    # ---------------------------------------------------------------- compat

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
