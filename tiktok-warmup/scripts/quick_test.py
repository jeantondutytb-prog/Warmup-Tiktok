"""Test rapide (~1-2 min) : chaque action du warmup une fois, avec captures.

Au lieu d'une session de 18 minutes, on enchaîne une fois chaque geste
(retour fil, scroll, recherche, résultat, like, commentaire, profil) et on
garde une capture pleine taille avant/après chaque étape dans
db/quicktest/<horodatage>/. Rien n'est écrit dans la base.

    venv/bin/python -m scripts.quick_test antoine.ckts [--comment] [--follow]
"""

import asyncio
import base64
import datetime
import io
import os
import sys
import time

from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from app.config import load_accounts, load_comments, load_keywords  # noqa: E402
from app.core.action_engine import ActionEngine, CaptchaDetected  # noqa: E402
from app.core.appium_driver import AppiumDriverManager  # noqa: E402
from app.core.coords import load_coords  # noqa: E402
from app.core import protocol  # noqa: E402


async def main(username: str, do_comment: bool, do_follow: bool) -> None:
    cfg = os.path.join(ROOT, "config")
    accounts = load_accounts(os.path.join(cfg, "accounts.yaml"))
    acc = next((a for a in accounts if a["username"] == username), None)
    if acc is None:
        sys.exit(f"compte inconnu : {username}")
    if acc.get("protected"):
        sys.exit(f"{username} est protégé — test refusé")

    stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    out = os.path.join(ROOT, "db", "quicktest", f"{stamp}-{username}")
    os.makedirs(out, exist_ok=True)

    driver = await asyncio.to_thread(AppiumDriverManager().create_session, {}, "quicktest")
    engine = ActionEngine(
        driver, load_comments(os.path.join(cfg, "comments.txt")),
        acc.get("comment_style", "casual"),
        load_coords(os.path.join(cfg, "coords.yaml")),
    )
    n = 0
    t0 = time.monotonic()
    report: list[tuple[str, str]] = []

    async def shot(label: str) -> None:
        nonlocal n
        n += 1
        b64 = await asyncio.to_thread(driver.get_screenshot_as_base64)
        Image.open(io.BytesIO(base64.b64decode(b64))).save(
            os.path.join(out, f"{n:02d}-{label}.png"))

    async def step(name: str, coro) -> str:
        await shot(f"{name}-avant")
        try:
            res = await coro
        except CaptchaDetected as e:
            await shot(f"{name}-captcha")
            report.append((name, f"CAPTCHA — {e}"))
            print(f"\n⛔ {name} : {e}", flush=True)
            raise
        except Exception as e:  # noqa: BLE001
            res = f"EXCEPTION {type(e).__name__}: {e}"
        await shot(f"{name}-apres")
        res = str(res)
        report.append((name, res))
        print(f"[{time.monotonic() - t0:5.1f}s] {name:<16} → {res}", flush=True)
        return res

    known = [a["username"] for a in accounts]
    try:
        r = await step("bascule", engine.switch_tiktok_account(username, known))
        if r:
            print("bascule impossible, arrêt")
            return
        await step("retour_fil", engine.return_to_feed())
        await step("scroll", engine.scroll_feed())
        await step("heart_avant", engine._heart_is_red())
        await step("like_fil", engine.like_video())
        await step("heart_apres", engine._heart_is_red())

        kw = protocol.flatten_keywords(load_keywords(os.path.join(cfg, "keywords.yaml")))[0]
        await step("recherche", engine.open_search(kw))
        await step("resultat", engine.open_first_result())
        await asyncio.sleep(3)
        await step("like_recherche", engine.like_video())
        await step("scroll_rech", engine.scroll_feed())
        await step("like_recherche2", engine.like_video())
        if do_comment:
            await step("commentaire", engine.comment_on_video())
        await step("profil", engine.open_creator_profile())
        if do_follow:
            # Même ordre que la phase profils : la grille d'abord, puis l'abonnement.
            await step("grille", engine.browse_profile_grid())
            await step("follow", engine.follow_from_profile())
        await step("retour_fil2", engine.return_to_feed())
    except CaptchaDetected:
        pass
    finally:
        print(f"\nCaptures : {out}  ({time.monotonic() - t0:.0f}s)")
        with open(os.path.join(out, "rapport.txt"), "w") as f:
            f.writelines(f"{a}\t{b}\n" for a, b in report)
        try:
            driver.quit()
        except Exception:  # noqa: BLE001
            pass


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if not args:
        sys.exit(__doc__)
    asyncio.run(main(args[0], "--comment" in sys.argv, "--follow" in sys.argv))
