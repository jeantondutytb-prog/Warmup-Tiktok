"""Gestion du cycle de vie Playwright et des cookies par compte TikTok."""

import json
import os
import random


VIEWPORTS = [
    {"width": 1366, "height": 768},
    {"width": 1440, "height": 900},
    {"width": 1280, "height": 800},
    {"width": 1536, "height": 864},
]

USER_AGENTS = [
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/127.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36"
    ),
]

_LAUNCH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--no-first-run",
    "--no-default-browser-check",
    "--disable-infobars",
]


class BrowserManager:
    """Lance Chromium via Playwright, gère les cookies par compte."""

    def __init__(self, cookies_dir: str):
        self.cookies_dir = cookies_dir
        os.makedirs(cookies_dir, exist_ok=True)
        self._playwright = None
        self._login_sessions: dict[str, tuple] = {}

    def _cookie_path(self, username: str) -> str:
        safe = username.replace("/", "_").replace("\\", "_")
        return os.path.join(self.cookies_dir, f"{safe}.json")

    def has_cookies(self, username: str) -> bool:
        return os.path.isfile(self._cookie_path(username))

    async def _ensure_playwright(self):
        if self._playwright is None:
            from playwright.async_api import async_playwright
            self._playwright = await async_playwright().start()
        return self._playwright

    async def create_context(self, username: str):
        """Crée un contexte headless pour le warmup."""
        pw = await self._ensure_playwright()
        browser = await pw.chromium.launch(headless=True, args=_LAUNCH_ARGS)
        viewport = random.choice(VIEWPORTS)
        ua = random.choice(USER_AGENTS)
        context = await browser.new_context(
            viewport=viewport,
            user_agent=ua,
            locale="fr-FR",
            timezone_id="Europe/Paris",
        )
        context._browser_ref = browser
        path = self._cookie_path(username)
        if os.path.isfile(path):
            with open(path) as f:
                cookies = json.load(f)
            await context.add_cookies(cookies)
        return context

    async def close_context(self, context) -> None:
        """Ferme le contexte ET son browser dédié."""
        browser = getattr(context, "_browser_ref", None)
        try:
            await context.close()
        except Exception:
            pass
        if browser:
            try:
                await browser.close()
            except Exception:
                pass

    async def save_cookies(self, context, username: str) -> None:
        cookies = await context.cookies()
        path = self._cookie_path(username)
        with open(path, "w") as f:
            json.dump(cookies, f, indent=2)

    async def start_login(self, username: str) -> None:
        """Ouvre un Chromium visible pour que l'utilisateur se connecte à TikTok."""
        pw = await self._ensure_playwright()
        browser = await pw.chromium.launch(headless=False, args=_LAUNCH_ARGS)
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            user_agent=random.choice(USER_AGENTS),
            locale="fr-FR",
            timezone_id="Europe/Paris",
        )
        page = await context.new_page()
        try:
            from playwright_stealth import Stealth
            await Stealth().apply_stealth_async(page)
        except Exception:
            pass
        await page.goto("https://www.tiktok.com/login", wait_until="domcontentloaded")
        self._login_sessions[username] = (browser, context, page)

    async def finish_login(self, username: str) -> None:
        """Sauvegarde les cookies après connexion manuelle, puis ferme le contexte."""
        if username not in self._login_sessions:
            raise ValueError(f"pas de session de connexion pour {username}")
        browser, context, page = self._login_sessions.pop(username)
        try:
            if page.is_closed():
                raise ValueError(
                    "Le navigateur a été fermé avant la sauvegarde. "
                    "Clique « Se connecter » à nouveau, connecte-toi, "
                    "puis « Sauvegarder » sans fermer le navigateur."
                )
            await self.save_cookies(context, username)
        finally:
            try:
                await context.close()
            except Exception:
                pass
            try:
                await browser.close()
            except Exception:
                pass

    def is_logging_in(self, username: str) -> bool:
        return username in self._login_sessions

    async def close(self) -> None:
        for username in list(self._login_sessions):
            browser, ctx, _ = self._login_sessions.pop(username)
            try:
                await ctx.close()
            except Exception:
                pass
            try:
                await browser.close()
            except Exception:
                pass
        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception:
                pass
            self._playwright = None
