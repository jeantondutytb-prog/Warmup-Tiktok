import asyncio
import datetime
import logging
import random
from sqlalchemy import create_engine, func
from sqlalchemy.orm import sessionmaker
from app.models.models import Base, Account, WarmupSession, ActionLog, migrate
from app.config import load_accounts, load_devices, load_comments, load_keywords
from app.core.anti_detect import human_delay, is_in_activity_window, get_allowed_actions
from app.core.coords import load_coords, UncalibratedPoint
from app.core import protocol
from app.core.appium_driver import AppiumDriverManager
from app.core.action_engine import ActionEngine, CaptchaDetected
from app.core.browser_manager import BrowserManager
import os

logger = logging.getLogger(__name__)

# Nombre de likes manqués d'affilée avant d'abandonner la phase de recherche.
MISSED_LIKES_BEFORE_ABORT = 2

# Profils qui ne s'ouvrent pas avant d'abandonner la phase profils.
MISSED_PROFILES_BEFORE_ABORT = 2

# Bascules ratées avant que le roulement laisse un compte de côté pour la
# journée : un compte absent du sélecteur de l'app ne réapparaîtra pas seul.
MAX_SWITCH_FAILURES = 2

# Les repères que la bascule de compte et les quatre phases tapent réellement.
# La garde de démarrage ne vérifie que ceux-là : exiger la calibration de
# points inutilisés (le partage) bloquerait le warmup pour rien.
REQUIRED_POINTS = (
    "home_tab",
    "profile_tab",
    "display_name",
    "search_icon",
    "result_first",
    "btn_like",
    "creator_avatar",
    "btn_follow_profile",
    "profile_grid_cell",
)


class Orchestrator:
    def __init__(self, db_url: str, config_dir: str, appium_url: str = "http://localhost:4723"):
        self.engine = create_engine(db_url, connect_args={"check_same_thread": False})
        Base.metadata.create_all(self.engine)
        migrate(self.engine)
        self.Session = sessionmaker(bind=self.engine)

        self.config_dir = config_dir
        self.accounts_config = load_accounts(os.path.join(config_dir, "accounts.yaml"))
        self.devices = load_devices(os.path.join(config_dir, "devices.yaml"))
        self.comments = load_comments(os.path.join(config_dir, "comments.txt"))
        self.keywords = load_keywords(os.path.join(config_dir, "keywords.yaml"))
        self.coords = load_coords(os.path.join(config_dir, "coords.yaml"))
        self.appium_manager = AppiumDriverManager(appium_url)
        self.fyp_shots_dir = os.path.join(os.path.dirname(config_dir), "db", "fyp")
        self.browser_manager = BrowserManager(
            os.path.join(os.path.dirname(config_dir), "config", "browser_cookies")
        )

        self._cycle_task: asyncio.Task | None = None
        self._subscribers: list[asyncio.Queue] = []
        self._stop_event = asyncio.Event()
        self._browser_tasks: dict[str, asyncio.Task] = {}
        self._browser_stops: dict[str, asyncio.Event] = {}

        self._rotation: dict = {"running": False, "current": None, "next_at": None, "message": ""}
        self._rotation_cursor = 0
        self._switch_failures: dict[str, int] = {}

        self._init_accounts()

    def _init_accounts(self):
        with self.Session() as session:
            for acc_cfg in self.accounts_config:
                existing = session.query(Account).filter_by(username=acc_cfg["username"]).first()
                if existing is None:
                    session.add(Account(
                        username=acc_cfg["username"],
                        device_profile=acc_cfg["device_profile"],
                        comment_style=acc_cfg.get("comment_style", "casual"),
                        role=acc_cfg.get("role", "flagship"),
                        protected=bool(acc_cfg.get("protected", False)),
                    ))
                else:
                    # Le rôle et la protection viennent du YAML, qui fait foi :
                    # retirer `protected` doit rester un geste explicite.
                    existing.role = acc_cfg.get("role", existing.role)
                    existing.protected = bool(acc_cfg.get("protected", False))
            session.commit()

    def get_status(self) -> dict[str, dict]:
        result = {}
        with self.Session() as session:
            for acc_cfg in self.accounts_config:
                username = acc_cfg["username"]
                account = session.query(Account).filter_by(username=username).first()
                if not account:
                    continue

                logs = (
                    session.query(ActionLog)
                    .join(WarmupSession)
                    .filter(WarmupSession.account_id == account.id)
                    .order_by(ActionLog.timestamp.desc())
                    .limit(20)
                    .all()
                )

                all_logs = (
                    session.query(ActionLog)
                    .join(WarmupSession)
                    .filter(WarmupSession.account_id == account.id)
                    .all()
                )
                counters = {"likes": 0, "follows": 0, "comments": 0, "videos_watched": 0, "scrolls": 0}
                for log in all_logs:
                    if log.action_type == "like":
                        counters["likes"] += 1
                    elif log.action_type == "follow":
                        counters["follows"] += 1
                    elif log.action_type == "comment":
                        counters["comments"] += 1
                    elif log.action_type == "watch":
                        counters["videos_watched"] += 1
                    elif log.action_type == "scroll":
                        counters["scrolls"] += 1

                last_session = (
                    session.query(WarmupSession)
                    .filter(WarmupSession.account_id == account.id)
                    .order_by(WarmupSession.started_at.desc())
                    .first()
                )
                counts_24h, _ = self._counts_24h(account.id)

                result[username] = {
                    "status": account.status,
                    "ramp_up_day": account.ramp_up_day,
                    "protocol_day": self._protocol_day(session, account),
                    "role": account.role,
                    "protected": bool(account.protected),
                    "used_24h": {
                        "likes": counts_24h.get("like", 0),
                        "follows": counts_24h.get("follow", 0),
                        "comments": counts_24h.get("comment", 0),
                    },
                    "caps_24h": {
                        "likes": protocol.DAILY_CAPS["like"],
                        "follows": protocol.DAILY_CAPS["follow"],
                        "comments": protocol.DAILY_CAPS["comment"],
                    },
                    "last_session": None if last_session is None else {
                        "id": last_session.id,
                        "keyword": last_session.keyword,
                        "started_at": last_session.started_at.isoformat(),
                        "completed": bool(last_session.completed),
                        "fyp_niche_count": last_session.fyp_niche_count,
                        "fyp_verdict": last_session.fyp_verdict,
                    },
                    "counters": counters,
                    "recent_logs": [
                        {"action": l.action_type, "detail": l.detail, "time": l.timestamp.isoformat()}
                        for l in logs
                    ],
                }
        return result

    def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers.append(queue)
        return queue

    async def _broadcast(self, event: dict):
        dead = []
        for i, q in enumerate(self._subscribers):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                dead.append(i)
        for i in reversed(dead):
            self._subscribers.pop(i)

    async def start_account(self, username: str, force: bool = False):
        if self._cycle_task and not self._cycle_task.done():
            return
        self._stop_event.clear()
        self._cycle_task = asyncio.create_task(self._run_cycle(username, force=force))

    async def stop_account(self, username: str):
        await self.stop_all()

    async def start_all(self):
        """Démarre le roulement iPhone sur tous les comptes non protégés."""
        if self._cycle_task and not self._cycle_task.done():
            return
        self._stop_event.clear()
        self._switch_failures.clear()
        self._cycle_task = asyncio.create_task(self._run_rotation())

    def rotation_status(self) -> dict:
        return dict(self._rotation)

    def _next_rotation_account(self) -> tuple[str | None, datetime.timedelta | None, str]:
        """Le prochain compte que la cadence autorise, en tourniquet.

        Sans compte disponible, renvoie l'attente la plus courte, ou None si
        tous les comptes ont épuisé leurs sessions du jour.
        """
        names = [a["username"] for a in self.accounts_config if not a.get("protected")]
        waits = []
        for i in range(len(names)):
            name = names[(self._rotation_cursor + i) % len(names)]
            if self._switch_failures.get(name, 0) >= MAX_SWITCH_FAILURES:
                continue
            gate = self._cadence_gate(name)
            if gate.ok:
                self._rotation_cursor = (self._rotation_cursor + i + 1) % len(names)
                return name, None, ""
            if gate.retry_after:
                waits.append(gate.retry_after)
        if waits:
            return None, min(waits), "en attente du prochain compte disponible"
        return None, None, "tous les comptes ont fait leurs sessions du jour"

    async def _rotation_wait(self, delay: datetime.timedelta, message: str) -> None:
        until = datetime.datetime.now() + delay
        self._rotation.update(current=None, next_at=until.isoformat(timespec="minutes"),
                              message=message)
        await self._broadcast({
            "type": "rotation", "username": "",
            "data": f"{message} — reprise à {until:%H:%M}",
            "timestamp": datetime.datetime.now().isoformat(),
        })
        try:
            await asyncio.wait_for(self._stop_event.wait(), timeout=delay.total_seconds())
        except asyncio.TimeoutError:
            pass

    async def _run_rotation(self):
        self._rotation.update(running=True, message="démarrage")
        day = datetime.date.today()
        device_failures = 0
        try:
            while not self._stop_event.is_set():
                now = datetime.datetime.now()
                if now.date() != day:
                    day = now.date()
                    self._switch_failures.clear()

                if not protocol.ROTATION_START_HOUR <= now.hour < protocol.ROTATION_END_HOUR:
                    resume = now.replace(hour=protocol.ROTATION_START_HOUR, minute=0,
                                         second=0, microsecond=0)
                    if now.hour >= protocol.ROTATION_END_HOUR:
                        resume += datetime.timedelta(days=1)
                    await self._rotation_wait(resume - now, "hors plage horaire")
                    continue

                name, wait, message = self._next_rotation_account()
                if name is None:
                    if wait is None:
                        resume = (now + datetime.timedelta(days=1)).replace(
                            hour=protocol.ROTATION_START_HOUR, minute=0, second=0, microsecond=0)
                        wait = resume - now
                    await self._rotation_wait(wait, message)
                    continue

                self._rotation.update(current=name, next_at=None, message="session en cours")
                outcome = await self._run_cycle(name)

                if outcome == "config":
                    self._rotation["message"] = "arrêté — calibration requise"
                    return
                if outcome == "captcha":
                    # Un CAPTCHA vise l'appareil autant que le compte : on ne
                    # bascule pas sur le suivant pour continuer comme si de rien.
                    self._rotation["message"] = f"arrêté — CAPTCHA TikTok sur @{name}, à résoudre à la main"
                    return
                if outcome == "device":
                    device_failures += 1
                    await self._rotation_wait(
                        datetime.timedelta(minutes=min(2 * device_failures, 15)),
                        "iPhone injoignable, nouvel essai",
                    )
                    continue
                device_failures = 0
                if outcome == "switch":
                    self._switch_failures[name] = self._switch_failures.get(name, 0) + 1
                if outcome == "ok":
                    lo, hi = protocol.ROTATION_JITTER
                    pause = protocol.MIN_GAP_BETWEEN_ACCOUNTS + datetime.timedelta(
                        seconds=random.uniform(lo.total_seconds(), hi.total_seconds()))
                    await self._rotation_wait(pause, "pause entre deux comptes")
                else:
                    await self._rotation_wait(datetime.timedelta(minutes=1), "passage au compte suivant")
        finally:
            self._rotation.update(running=False, current=None, next_at=None)
            await self._broadcast({
                "type": "rotation", "username": "", "data": "roulement arrêté",
                "timestamp": datetime.datetime.now().isoformat(),
            })

    async def stop_all(self):
        self._stop_event.set()
        for stop in self._browser_stops.values():
            stop.set()
        if self._cycle_task:
            self._cycle_task.cancel()
            try:
                await self._cycle_task
            except asyncio.CancelledError:
                pass
            self._cycle_task = None
        for username, task in list(self._browser_tasks.items()):
            if not task.done():
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
        self._browser_tasks.clear()
        self._browser_stops.clear()
        with self.Session() as session:
            for acc_cfg in self.accounts_config:
                account = session.query(Account).filter_by(username=acc_cfg["username"]).first()
                if account:
                    account.status = "idle"
            session.commit()
        for acc_cfg in self.accounts_config:
            await self._broadcast({
                "type": "status", "username": acc_cfg["username"],
                "data": "idle", "timestamp": datetime.datetime.now().isoformat(),
            })

    async def _run_cycle(self, target_username: str | None = None, force: bool = False) -> str:
        """Une session iPhone. Renvoie ok, refused, config, device, switch, captcha ou error."""
        if target_username:
            acc_cfg = next((a for a in self.accounts_config if a["username"] == target_username), None)
        else:
            acc_cfg = self.accounts_config[0]
        if not acc_cfg:
            return "config"
        username = acc_cfg["username"]

        gate = self._cadence_gate(username)
        # Un compte protégé n'est jamais forçable : « ne pas toucher » n'est
        # pas une règle d'espacement, c'est une interdiction.
        if force and gate.ok is False and "protégé" not in gate.reason:
            await self._broadcast({
                "type": "session", "username": username,
                "data": f"cadence contournée volontairement — {gate.reason}",
                "timestamp": datetime.datetime.now().isoformat(),
            })
            gate = protocol.CadenceCheck(True)
        if not gate.ok:
            await self._broadcast({
                "type": "refused", "username": username,
                "data": gate.reason, "timestamp": datetime.datetime.now().isoformat(),
            })
            return "refused"

        missing = [p for p in REQUIRED_POINTS if p in self.coords.uncalibrated()]
        if missing:
            await self._set_error(
                username,
                "points non calibrés dans coords.yaml : " + ", ".join(missing)
                + " — lance `python -m scripts.calibrate` avec l'iPhone branché.",
            )
            return "config"

        try:
            driver = await asyncio.to_thread(
                self.appium_manager.create_session, {}, "cycle"
            )
        except Exception as e:
            await self._set_error(username, str(e))
            return "device"

        try:
            # TIKTOK_TRACE=1 fait enregistrer une capture après chaque tap,
            # dans db/trace/<horodatage>/. Indispensable pour savoir où une
            # session part de travers : les logs d'action ne le disent pas.
            trace_dir = None
            if os.environ.get("TIKTOK_TRACE"):
                stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
                trace_dir = os.path.join(
                    os.path.dirname(self.config_dir), "db", "trace", f"{stamp}-{username}"
                )
            action_engine = ActionEngine(
                driver, self.comments, acc_cfg.get("comment_style", "casual"),
                self.coords, trace_dir=trace_dir,
            )
            if trace_dir:
                await self._broadcast({
                    "type": "session", "username": username,
                    "data": f"traçage actif : {trace_dir}",
                    "timestamp": datetime.datetime.now().isoformat(),
                })

            with self.Session() as db:
                account = db.query(Account).filter_by(username=username).first()
                if account:
                    account.status = "running"
                    db.commit()
            await self._broadcast({
                "type": "status", "username": username,
                "data": "running", "timestamp": datetime.datetime.now().isoformat(),
            })

            known = [a["username"] for a in self.accounts_config]
            reason = await action_engine.switch_tiktok_account(username, known)
            if reason:
                await self._set_error(username, f"bascule vers @{username} impossible — {reason}")
                return "switch"
            await self._broadcast({
                "type": "session", "username": username,
                "data": f"compte vérifié à l'écran : @{username}",
                "timestamp": datetime.datetime.now().isoformat(),
            })

            await self._warmup_account(username, action_engine, driver)
            return "ok"

        except asyncio.CancelledError:
            return "error"
        except CaptchaDetected as e:
            await self._set_error(username, str(e))
            return "captcha"
        except Exception as e:
            await self._set_error(username, str(e))
            return "device" if isinstance(e, (ConnectionError, OSError)) else "error"
        finally:
            with self.Session() as db:
                account = db.query(Account).filter_by(username=username).first()
                if account:
                    account.status = "idle"
                    db.commit()
            await self._broadcast({
                "type": "status", "username": username,
                "data": "idle", "timestamp": datetime.datetime.now().isoformat(),
            })
            await asyncio.to_thread(self.appium_manager.close_session, driver)

    # ------------------------------------------------------------- cadence

    def _protocol_day(self, db, account: Account) -> int:
        """Jour de protocole, compté depuis la première session du compte.

        N'avance que vers l'avant : un jour posé à la main au-delà du calcul
        est conservé.
        """
        first = (
            db.query(func.min(WarmupSession.started_at))
            .filter(WarmupSession.account_id == account.id)
            .scalar()
        )
        if first is not None:
            elapsed = (datetime.date.today() - first.date()).days + 1
            computed = min(elapsed, protocol.PROTOCOL_DAYS)
            if computed > account.protocol_day:
                account.protocol_day = computed
                db.commit()
        return account.protocol_day

    def _cadence_gate(self, username: str) -> protocol.CadenceCheck:
        """Applique les règles de cadence du protocole avant d'ouvrir une session."""
        with self.Session() as db:
            account = db.query(Account).filter_by(username=username).first()
            if account is None:
                return protocol.CadenceCheck(False, f"compte inconnu : {username}")

            now = datetime.datetime.now()
            midnight = now.replace(hour=0, minute=0, second=0, microsecond=0)

            sessions_today = (
                db.query(WarmupSession)
                .filter(WarmupSession.account_id == account.id)
                .filter(WarmupSession.started_at >= midnight)
                .count()
            )
            last_this = (
                db.query(WarmupSession.started_at)
                .filter(WarmupSession.account_id == account.id)
                .order_by(WarmupSession.started_at.desc())
                .limit(1)
                .scalar()
            )
            last_any = (
                db.query(WarmupSession.started_at)
                .filter(WarmupSession.account_id != account.id)
                .order_by(WarmupSession.started_at.desc())
                .limit(1)
                .scalar()
            )

            return protocol.can_start_session(
                protocol_day=self._protocol_day(db, account),
                sessions_today=sessions_today,
                last_session_this_account=last_this,
                last_session_any_account=last_any,
                protected=bool(account.protected),
                now=now,
            )

    def _counts_24h(self, account_id: int) -> tuple[dict[str, int], list[datetime.datetime]]:
        """Actions des 24 dernières heures, et l'horodatage de chaque abonnement.

        La fenêtre est glissante, pas calendaire : les plafonds du protocole
        sont exprimés « par 24 h », et minuit ne remet rien à zéro côté TikTok.
        """
        cutoff = datetime.datetime.now() - datetime.timedelta(hours=24)
        counts: dict[str, int] = {}
        follow_times: list[datetime.datetime] = []
        with self.Session() as db:
            rows = (
                db.query(ActionLog.action_type, ActionLog.timestamp)
                .join(WarmupSession, ActionLog.session_id == WarmupSession.id)
                .filter(WarmupSession.account_id == account_id)
                .filter(ActionLog.timestamp >= cutoff)
                .all()
            )
        for action_type, timestamp in rows:
            counts[action_type] = counts.get(action_type, 0) + 1
            if action_type == "follow":
                follow_times.append(timestamp)
        return counts, follow_times

    def _session_index(self, account_id: int) -> int:
        with self.Session() as db:
            return (
                db.query(WarmupSession)
                .filter(WarmupSession.account_id == account_id)
                .count()
            )

    # ------------------------------------------------------------- session

    async def _warmup_account(self, username: str, action_engine: ActionEngine, driver,
                              stop_event: asyncio.Event | None = None):
        """Exécute une session de 18 minutes, phase par phase."""
        stop = stop_event or self._stop_event
        with self.Session() as db:
            account = db.query(Account).filter_by(username=username).first()
            account_id = account.id
            protocol_day = self._protocol_day(db, account)

        # La montée en charge du protocole prime sur les plafonds 24 h : aux
        # jours 1-2 un compte ne fait que regarder et scroller. Un plafond de
        # 25 likes ne vaut rien si l'action n'est pas encore débloquée.
        allowed = set(get_allowed_actions(protocol_day))

        counts_24h, follow_times = self._counts_24h(account_id)
        budget = protocol.SessionBudget(
            like_cap=protocol.daily_cap("like"),
            follow_cap=protocol.daily_cap("follow"),
            comment_cap=protocol.daily_cap("comment"),
            likes_24h=counts_24h.get("like", 0),
            follows_24h=counts_24h.get("follow", 0),
            comments_24h=counts_24h.get("comment", 0),
            follow_times=follow_times,
        )

        keyword = protocol.keyword_for_session(self.keywords, self._session_index(account_id))

        with self.Session() as db:
            ws = WarmupSession(
                account_id=account_id,
                started_at=datetime.datetime.now(),
                keyword=keyword,
            )
            db.add(ws)
            db.commit()
            db.refresh(ws)
            session_id = ws.id

        await self._broadcast({
            "type": "session", "username": username,
            "data": (
                f"session #{session_id} — jour {protocol_day}/14 · "
                f"mot-clé « {keyword} » · actions débloquées : {', '.join(sorted(allowed))} · "
                f"plafonds 24h : {budget.likes_24h}/{budget.like_cap} likes, "
                f"{budget.follows_24h}/{budget.follow_cap} abonnements"
            ),
            "timestamp": datetime.datetime.now().isoformat(),
        })

        loop = asyncio.get_event_loop()
        started = loop.time()

        def elapsed() -> float:
            return loop.time() - started

        runners = {
            "fyp_entry": self._phase_fyp_entry,
            "search": self._phase_search,
            "profiles": self._phase_profiles,
            "fyp_measure": self._phase_fyp_measure,
        }

        completed = True
        try:
            for phase in protocol.PHASES:
                if stop.is_set():
                    completed = False
                    break
                await self._broadcast({
                    "type": "phase", "username": username,
                    "data": f"{phase.label} ({phase.start_s // 60}–{phase.end_s // 60}′)",
                    "timestamp": datetime.datetime.now().isoformat(),
                })
                await runners[phase.name](
                    username=username, session_id=session_id, engine=action_engine,
                    budget=budget, keyword=keyword, phase=phase, elapsed=elapsed,
                    allowed=allowed, stop_event=stop,
                )
            else:
                completed = not stop.is_set()
        except BaseException:
            # Annulée par stop_all, ou interrompue par une erreur (CAPTCHA…) :
            # la session est écourtée, pas finie.
            completed = False
            raise
        finally:
            with self.Session() as db:
                ws = db.get(WarmupSession, session_id)
                ws.ended_at = datetime.datetime.now()
                ws.duration_seconds = int((ws.ended_at - ws.started_at).total_seconds())
                ws.completed = completed
                db.commit()

    async def _phase_fyp_entry(self, *, username, session_id, engine, budget, phase, elapsed, allowed=None, stop_event=None, **_):
        """0–2′ : trois ou quatre vidéos du fil, en entier, même hors niche.

        On arrive comme un utilisateur, pas comme un opérateur — et rien de
        plus. Le document dit « en entier, même hors niche », mais il est
        écrit pour un compte au fil neutre. Sur eva.drtp, dont le fil est
        saturé de contenu « trend 10k » hérité du script d'août, regarder en
        entier avec replay renforçait à pleine puissance exactement ce qu'on
        cherche à effacer. Ici on ne fait que traverser.

        La phase commence par revenir au fil. Rien ne garantit sur quel écran
        l'app a été laissée — un profil, une recherche, un réglage. La session
        #44 a démarré sur la page profil, y a scrollé la grille deux minutes
        en croyant lire le fil, puis a ouvert le menu hamburger : sur un
        profil, la loupe du fil est le ☰.
        """
        detail = await engine.return_to_feed()
        await self._record(session_id, username, "watch",
                           "SKIP" if detail == "SKIP" else f"départ : {detail}")

        watched = 0
        _stop = stop_event or self._stop_event
        while elapsed() < phase.end_s and not _stop.is_set() and watched < 4:
            detail = await engine.watch_briefly()
            await self._record(session_id, username, "watch", detail)
            watched += 1
            if elapsed() >= phase.end_s:
                break
            await self._record(session_id, username, "scroll", await engine.scroll_feed())
        await self._sleep_until(phase.end_s, elapsed, stop_event=_stop)

    async def _phase_search(self, *, username, session_id, engine, budget, keyword, phase, elapsed, allowed=None, stop_event=None, **_):
        """2–10′ : un seul mot-clé, vidéos regardées en entier, ~1 like sur 3."""
        search_ok = False
        try:
            search_detail = await engine.open_search(keyword)
            await self._record(session_id, username, "search", search_detail)
            if not search_detail.startswith("SKIP"):
                opened = await engine.open_first_result()
                await self._record(session_id, username, "search", opened)
                search_ok = not opened.startswith("SKIP")
        except UncalibratedPoint as e:
            await self._record(session_id, username, "search", f"SKIP — {e}")
            await self._sleep_until(phase.end_s, elapsed, stop_event=stop_event)
            return

        _stop = stop_event or self._stop_event
        if not search_ok:
            await self._record(session_id, username, "search",
                               "SKIP — recherche échouée, repli sur le FYP")
            detail = await engine.return_to_feed()
            if detail.startswith("SKIP"):
                await self._sleep_until(phase.end_s, elapsed, stop_event=_stop)
                return
            await self._phase_fyp_entry(
                username=username, session_id=session_id, engine=engine,
                budget=budget, phase=phase, elapsed=elapsed, allowed=allowed,
                stop_event=_stop,
            )
            return

        missed = 0
        scroll_fails = 0
        while elapsed() < phase.end_s and not _stop.is_set():
            await self._record(session_id, username, "watch", await engine.watch_fully())
            if elapsed() >= phase.end_s:
                break

            can_like_today = allowed is None or "like" in allowed
            if can_like_today and protocol.should_like_in_search() and budget.can_like():
                detail = await engine.like_video()
                if detail.startswith("SKIP"):
                    await self._record(session_id, username, "like", detail)
                    if "deux taps" in detail:
                        missed += 1
                        if missed >= MISSED_LIKES_BEFORE_ABORT:
                            await self._record(
                                session_id, username, "search",
                                f"SKIP — {missed} likes manqués d'affilée, "
                                "l'écran n'est pas une vidéo : phase abandonnée",
                            )
                            await self._sleep_until(phase.end_s, elapsed, stop_event=_stop)
                            return
                else:
                    missed = 0
                    budget.record_like()
                    await self._record(session_id, username, "like", detail)

            can_comment_today = allowed is None or "comment" in allowed
            if can_comment_today and protocol.should_comment_in_search() and budget.can_comment():
                detail = await engine.comment_on_video()
                if not detail.startswith("SKIP"):
                    budget.record_comment()
                await self._record(session_id, username, "comment", detail)

            scroll_detail = await engine.scroll_feed()
            await self._record(session_id, username, "scroll", scroll_detail)
            if scroll_detail.startswith("SKIP"):
                scroll_fails += 1
                if scroll_fails >= 3:
                    await self._record(session_id, username, "search",
                                       "SKIP — page morte (3 scrolls échoués), repli sur le FYP")
                    detail = await engine.return_to_feed()
                    if detail.startswith("SKIP"):
                        await self._sleep_until(phase.end_s, elapsed, stop_event=_stop)
                        return
                    scroll_fails = 0
            else:
                scroll_fails = 0
        await self._sleep_until(phase.end_s, elapsed, stop_event=_stop)

    async def _phase_profiles(self, *, username, session_id, engine, budget, phase, elapsed, allowed=None, stop_event=None, **_):
        """10–13′ : deux ou trois profils, 2–3 abonnements max, jamais d'affilée.

        Sautée tant que la montée en charge n'a pas débloqué la visite de
        profil : aux jours 1-4 le compte se contente de regarder le fil.
        """
        _stop = stop_event or self._stop_event
        if allowed is not None and "visit_profile" not in allowed:
            await self._record(
                session_id, username, "visit_profile",
                "SKIP — visite de profil pas encore débloquée par la montée en charge",
            )
            await self._phase_fyp_entry(
                username=username, session_id=session_id, engine=engine,
                budget=budget, phase=phase, elapsed=elapsed, allowed=allowed,
                stop_event=_stop,
            )
            return
        missed_profiles = 0
        while (
            elapsed() < phase.end_s
            and not _stop.is_set()
            and budget.profiles_remaining() > 0
        ):
            feed_detail = await engine.return_to_feed()
            if feed_detail.startswith("SKIP"):
                await self._record(session_id, username, "visit_profile",
                                   f"SKIP — impossible de revenir au fil : {feed_detail}")
                break
            for _ in range(random.randint(1, 4)):
                await engine.scroll_feed()

            try:
                profile_detail = await engine.open_creator_profile()
                await self._record(session_id, username, "visit_profile", profile_detail)
                if profile_detail.startswith("SKIP"):
                    # Un avatar manqué (live, pub, carrousel) ne condamne pas
                    # la phase : on retente depuis le fil, deux fois au plus.
                    missed_profiles += 1
                    if missed_profiles >= MISSED_PROFILES_BEFORE_ABORT:
                        break
                    continue
                await self._record(session_id, username, "visit_profile", await engine.browse_profile_grid())
            except UncalibratedPoint as e:
                await self._record(session_id, username, "visit_profile", f"SKIP — {e}")
                break

            followed = False
            may_follow, reason = budget.can_follow()
            if allowed is not None and "follow" not in allowed:
                may_follow, reason = False, "abonnement pas encore débloqué"
            if may_follow:
                detail = await engine.follow_from_profile()
                if detail.startswith("SKIP"):
                    await self._record(session_id, username, "follow", detail)
                else:
                    budget.record_follow()
                    followed = True
                    await self._record(session_id, username, "follow", detail)
            else:
                await self._record(session_id, username, "follow", f"SKIP — {reason}")

            budget.record_profile_visit(followed=followed)
            await engine.go_back()
            await asyncio.sleep(human_delay(1.0, 2.5))
        await self._sleep_until(phase.end_s, elapsed, stop_event=_stop)

    async def _phase_fyp_measure(self, *, username, session_id, engine, phase, elapsed, allowed=None, stop_event=None, **_):
        """13–18′ : retour au FYP, 20 scrolls capturés pour comptage manuel."""
        _stop = stop_event or self._stop_event
        detail = await engine.return_to_feed()
        if detail.startswith("SKIP"):
            await self._record(
                session_id, username, "fyp_measure",
                f"SKIP — retour au fil échoué ({detail}), mesure abandonnée",
            )
            await self._sleep_until(phase.end_s, elapsed, stop_event=_stop)
            return
        await self._record(session_id, username, "fyp_measure", detail)

        shots_dir = os.path.join(self.fyp_shots_dir, str(session_id))
        taken, distinct = await engine.measure_fyp(shots_dir)
        note = f"{taken} captures, {distinct} vidéos distinctes dans {shots_dir}"
        if distinct < protocol.FYP_MEASURE_SCROLLS // 2:
            note += " — fil bloqué, mesure peu fiable"
        await self._record(session_id, username, "fyp_measure",
                           note + " — comptage à saisir sur le dashboard")
        await self._sleep_until(phase.end_s, elapsed, stop_event=_stop)

    async def _sleep_until(self, target_s: float, elapsed,
                          stop_event: asyncio.Event | None = None) -> None:
        """Tient la phase jusqu'à sa fin, sans dépasser sur la suivante."""
        _stop = stop_event or self._stop_event
        while elapsed() < target_s and not _stop.is_set():
            await asyncio.sleep(min(2.0, target_s - elapsed()))

    async def _record(self, session_id: int, username: str, action: str, detail: str) -> None:
        """Journalise une action déjà exécutée et la pousse au dashboard.

        Un refus n'entre jamais dans `action_logs` : ces lignes alimentent les
        plafonds 24 h, et compter un abonnement refusé comme un abonnement
        restreindrait la session du lendemain sur une action qui n'a pas eu
        lieu. Le refus reste visible au dashboard, en événement `refused`.
        """
        if detail == "SKIP" or detail.startswith("SKIP"):
            logger.warning("SKIP  %s | %s: %s", username, action, detail)
            await self._broadcast({
                "type": "refused", "username": username,
                "data": f"{action}: {detail}",
                "timestamp": datetime.datetime.now().isoformat(),
            })
            return
        with self.Session() as db:
            db.add(ActionLog(session_id=session_id, action_type=action, detail=detail))
            db.commit()
        await self._broadcast({
            "type": "action", "username": username,
            "data": f"{action}: {detail}",
            "timestamp": datetime.datetime.now().isoformat(),
        })

    async def _do_action(self, action_engine, action, username, session_id, action_counts):
        try:
            detail = await action_engine.execute_action(action)
        except ConnectionError:
            await self._broadcast({
                "type": "action", "username": username,
                "data": "WDA connection lost, recovering...",
                "timestamp": datetime.datetime.now().isoformat(),
            })
            self._stop_event.set()
            return
        if detail.startswith("SKIP"):
            return
        action_counts[action] = action_counts.get(action, 0) + 1
        with self.Session() as db:
            log = ActionLog(session_id=session_id, action_type=action, detail=detail)
            db.add(log)
            db.commit()
        await self._broadcast({
            "type": "action", "username": username,
            "data": f"{action}: {detail}",
            "timestamp": datetime.datetime.now().isoformat(),
        })

        with self.Session() as db:
            ws = db.query(WarmupSession).get(session_id)
            ws.ended_at = datetime.datetime.now()
            if ws.started_at:
                ws.duration_seconds = int((ws.ended_at - ws.started_at).total_seconds())
            db.commit()

    # --------------------------------------------------------- mesure FYP

    def pending_fyp(self) -> list[dict]:
        """Sessions terminées dont le comptage FYP n'a pas encore été saisi."""
        with self.Session() as db:
            rows = (
                db.query(WarmupSession, Account.username)
                .join(Account, WarmupSession.account_id == Account.id)
                .filter(WarmupSession.ended_at.isnot(None))
                .filter(WarmupSession.fyp_niche_count.is_(None))
                # Seules les sessions du protocole ont un mot-clé. Les sessions
                # d'avant la bascule n'ont jamais eu de phase de mesure : les
                # remonter noierait la file dans un historique sans captures.
                .filter(WarmupSession.keyword.isnot(None))
                .order_by(WarmupSession.started_at.desc())
                .all()
            )
        return [
            {
                "session_id": ws.id,
                "username": username,
                "keyword": ws.keyword,
                "started_at": ws.started_at.isoformat(),
                "shots_dir": os.path.join(self.fyp_shots_dir, str(ws.id)),
            }
            for ws, username in rows
        ]

    def record_fyp_count(self, session_id: int, niche_videos: int) -> dict:
        """Enregistre le comptage saisi à la main et en dérive le verdict."""
        if not 0 <= niche_videos <= protocol.FYP_MEASURE_SCROLLS:
            raise ValueError(
                f"le comptage doit être entre 0 et {protocol.FYP_MEASURE_SCROLLS}"
            )
        verdict = protocol.fyp_verdict(niche_videos)
        with self.Session() as db:
            ws = db.get(WarmupSession, session_id)
            if ws is None:
                raise KeyError(f"session inconnue : {session_id}")
            ws.fyp_niche_count = niche_videos
            ws.fyp_verdict = verdict
            db.commit()
        return {"session_id": session_id, "count": niche_videos, "verdict": verdict}

    def advance_protocol_day(self, username: str, day: int) -> dict:
        """Positionne le jour de protocole d'un compte (1..14)."""
        with self.Session() as db:
            account = db.query(Account).filter_by(username=username).first()
            if account is None:
                raise KeyError(f"compte inconnu : {username}")
            account.protocol_day = day
            db.commit()
        return {"username": username, "protocol_day": day}

    def add_account(self, username: str, role: str = "flagship",
                    comment_style: str = "casual", protected: bool = False) -> dict:
        """Ajoute un compte TikTok et le persiste dans accounts.yaml."""
        with self.Session() as db:
            existing = db.query(Account).filter_by(username=username).first()
            if existing:
                raise ValueError(f"le compte {username} existe déjà")
            account = Account(
                username=username,
                device_profile="iphone_xs",
                comment_style=comment_style,
                role=role,
                protected=protected,
            )
            db.add(account)
            db.commit()

        new_cfg = {
            "username": username,
            "device_profile": "iphone_xs",
            "comment_style": comment_style,
            "tiktok_row": len(self.accounts_config),
            "role": role,
            "protected": protected,
        }
        self.accounts_config.append(new_cfg)
        self._save_accounts_yaml()
        return {"username": username, "role": role}

    def delete_account(self, username: str) -> dict:
        """Supprime un compte s'il n'a aucune session."""
        with self.Session() as db:
            account = db.query(Account).filter_by(username=username).first()
            if account is None:
                raise KeyError(f"compte inconnu : {username}")
            has_sessions = db.query(WarmupSession).filter_by(account_id=account.id).count()
            if has_sessions:
                raise ValueError(
                    f"{username} a {has_sessions} session(s) — suppression interdite"
                )
            db.delete(account)
            db.commit()

        self.accounts_config = [a for a in self.accounts_config if a["username"] != username]
        self._save_accounts_yaml()
        return {"deleted": username}

    def _save_accounts_yaml(self) -> None:
        import yaml
        path = os.path.join(self.config_dir, "accounts.yaml")
        with open(path, "w") as f:
            yaml.dump({"accounts": self.accounts_config}, f,
                      default_flow_style=False, allow_unicode=True, sort_keys=False)

    # --------------------------------------------------------- mode navigateur PC

    async def start_account_browser(self, username: str, force: bool = False):
        """Démarre une session warmup via navigateur PC (Playwright)."""
        existing = self._browser_tasks.get(username)
        if existing and not existing.done():
            raise RuntimeError(f"session déjà en cours pour {username}")
        stop = asyncio.Event()
        self._browser_stops[username] = stop
        self._browser_tasks[username] = asyncio.create_task(
            self._run_cycle_browser(username, force=force, stop_event=stop)
        )

    async def start_all_browser(self, force: bool = False):
        """Démarre le warmup navigateur pour tous les comptes en parallèle."""
        started = []
        for acc_cfg in self.accounts_config:
            username = acc_cfg["username"]
            existing = self._browser_tasks.get(username)
            if existing and not existing.done():
                continue
            if not self.browser_manager.has_cookies(username):
                await self._broadcast({
                    "type": "refused", "username": username,
                    "data": f"pas de cookies pour {username} — connexion requise",
                    "timestamp": datetime.datetime.now().isoformat(),
                })
                continue
            stop = asyncio.Event()
            self._browser_stops[username] = stop
            self._browser_tasks[username] = asyncio.create_task(
                self._run_cycle_browser(username, force=force, stop_event=stop)
            )
            started.append(username)
        return started

    async def stop_account_browser(self, username: str):
        """Arrête la session navigateur d'un seul compte."""
        stop = self._browser_stops.get(username)
        if stop:
            stop.set()
        task = self._browser_tasks.get(username)
        if task and not task.done():
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._browser_tasks.pop(username, None)
        self._browser_stops.pop(username, None)

    async def _run_cycle_browser(self, target_username: str, force: bool = False,
                                stop_event: asyncio.Event | None = None):
        acc_cfg = next(
            (a for a in self.accounts_config if a["username"] == target_username), None
        )
        if not acc_cfg:
            return
        username = acc_cfg["username"]
        stop = stop_event or self._stop_event

        gate = self._cadence_gate(username)
        if force and gate.ok is False and "protégé" not in gate.reason:
            await self._broadcast({
                "type": "session", "username": username,
                "data": f"cadence contournée volontairement — {gate.reason}",
                "timestamp": datetime.datetime.now().isoformat(),
            })
            gate = protocol.CadenceCheck(True)
        if not gate.ok:
            await self._broadcast({
                "type": "refused", "username": username,
                "data": gate.reason,
                "timestamp": datetime.datetime.now().isoformat(),
            })
            return

        if not self.browser_manager.has_cookies(username):
            await self._set_error(
                username,
                "Pas de cookies — connecte-toi d'abord via « Se connecter »",
            )
            return

        with self.Session() as db:
            account = db.query(Account).filter_by(username=username).first()
            if account:
                account.status = "running"
                db.commit()
        await self._broadcast({
            "type": "status", "username": username,
            "data": "running",
            "timestamp": datetime.datetime.now().isoformat(),
        })

        context = None
        try:
            context = await self.browser_manager.create_context(username)
            page = await context.new_page()

            try:
                from playwright_stealth import Stealth
                await Stealth().apply_stealth_async(page)
            except Exception:
                pass

            await page.goto(
                "https://www.tiktok.com/foryou",
                wait_until="domcontentloaded", timeout=20000,
            )
            await asyncio.sleep(3)

            login_modal = False
            try:
                for text in ("Connecte-toi à TikTok", "Log in to TikTok"):
                    if await page.locator(f'text="{text}"').count() > 0:
                        login_modal = True
                        break
            except Exception:
                pass

            if "/login" in page.url or login_modal:
                await self._set_error(
                    username,
                    "Non connecté — clique « Se connecter » dans le mode "
                    "Navigateur PC, connecte-toi à TikTok, puis « Sauvegarder »",
                )
                if context:
                    await self.browser_manager.close_context(context)
                    context = None
                return

            trace_dir = None
            if os.environ.get("TIKTOK_TRACE"):
                stamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
                trace_dir = os.path.join(
                    os.path.dirname(self.config_dir),
                    "db", "trace", f"{stamp}-{username}-browser",
                )

            from app.core.browser_action_engine import BrowserActionEngine
            action_engine = BrowserActionEngine(
                page, self.comments, acc_cfg.get("comment_style", "casual"),
                trace_dir=trace_dir,
            )
            if trace_dir:
                await self._broadcast({
                    "type": "session", "username": username,
                    "data": f"traçage actif (navigateur) : {trace_dir}",
                    "timestamp": datetime.datetime.now().isoformat(),
                })

            await self._warmup_account(username, action_engine, driver=None,
                                       stop_event=stop)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            await self._set_error(username, str(e))
        finally:
            self._browser_tasks.pop(username, None)
            self._browser_stops.pop(username, None)
            with self.Session() as db:
                account = db.query(Account).filter_by(username=username).first()
                if account:
                    account.status = "idle"
                    db.commit()
            await self._broadcast({
                "type": "status", "username": username,
                "data": "idle",
                "timestamp": datetime.datetime.now().isoformat(),
            })
            if context:
                await self.browser_manager.save_cookies(context, username)
                await self.browser_manager.close_context(context)

    async def _set_error(self, username: str, error: str):
        logger.error("ERREUR %s | %s", username, error)
        with self.Session() as session:
            account = session.query(Account).filter_by(username=username).first()
            if account:
                account.status = "error"
                session.commit()
        await self._broadcast({
            "type": "error_event", "username": username,
            "data": error, "timestamp": datetime.datetime.now().isoformat(),
        })
