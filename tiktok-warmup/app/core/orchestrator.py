import asyncio
import datetime
import random
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models.models import Base, Account, WarmupSession, ActionLog, migrate
from app.config import load_accounts, load_devices, load_comments, load_keywords
from app.core.anti_detect import human_delay, is_in_activity_window, get_allowed_actions
from app.core.coords import load_coords, UncalibratedPoint
from app.core import protocol
from app.core.appium_driver import AppiumDriverManager
from app.core.action_engine import ActionEngine
import os

# Les repères que les quatre phases tapent réellement. La garde de démarrage
# ne vérifie que ceux-là : exiger la calibration de points inutilisés (le
# partage, le sélecteur de compte) bloquerait le warmup pour rien.
# Nombre de likes manqués d'affilée avant d'abandonner la phase de recherche.
MISSED_LIKES_BEFORE_ABORT = 2

REQUIRED_POINTS = (
    "home_tab",
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

        self._cycle_task: asyncio.Task | None = None
        self._subscribers: list[asyncio.Queue] = []
        self._stop_event = asyncio.Event()

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
                    "protocol_day": account.protocol_day,
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
        if self._cycle_task and not self._cycle_task.done():
            return
        self._stop_event.clear()
        self._cycle_task = asyncio.create_task(self._run_cycle())

    async def stop_all(self):
        self._stop_event.set()
        if self._cycle_task:
            self._cycle_task.cancel()
            try:
                await self._cycle_task
            except asyncio.CancelledError:
                pass
            self._cycle_task = None
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

    async def _run_cycle(self, target_username: str | None = None, force: bool = False):
        if target_username:
            acc_cfg = next((a for a in self.accounts_config if a["username"] == target_username), None)
        else:
            acc_cfg = self.accounts_config[0]
        if not acc_cfg:
            return
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
            return

        missing = [p for p in REQUIRED_POINTS if p in self.coords.uncalibrated()]
        if missing:
            await self._set_error(
                username,
                "points non calibrés dans coords.yaml : " + ", ".join(missing)
                + " — lance `python -m scripts.calibrate` avec l'iPhone branché.",
            )
            return

        try:
            driver = await asyncio.to_thread(
                self.appium_manager.create_session, {}, "cycle"
            )
        except Exception as e:
            await self._set_error(username, str(e))
            return

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

            await self._warmup_account(username, action_engine, driver)

        except asyncio.CancelledError:
            pass
        except Exception as e:
            await self._set_error(username, str(e))
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
                protocol_day=account.protocol_day,
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

    async def _warmup_account(self, username: str, action_engine: ActionEngine, driver):
        """Exécute une session de 18 minutes, phase par phase."""
        with self.Session() as db:
            account = db.query(Account).filter_by(username=username).first()
            account_id = account.id
            protocol_day = account.protocol_day

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
                if self._stop_event.is_set():
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
                    allowed=allowed,
                )
            else:
                completed = not self._stop_event.is_set()
        except asyncio.CancelledError:
            # stop_all annule la tâche : la session est écourtée, pas finie.
            completed = False
            raise
        finally:
            with self.Session() as db:
                ws = db.get(WarmupSession, session_id)
                ws.ended_at = datetime.datetime.now()
                ws.duration_seconds = int((ws.ended_at - ws.started_at).total_seconds())
                ws.completed = completed
                db.commit()

    async def _phase_fyp_entry(self, *, username, session_id, engine, budget, phase, elapsed, allowed=None, **_):
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
        while elapsed() < phase.end_s and not self._stop_event.is_set() and watched < 4:
            detail = await engine.watch_briefly()
            await self._record(session_id, username, "watch", detail)
            watched += 1
            if elapsed() >= phase.end_s:
                break
            await self._record(session_id, username, "scroll", await engine.scroll_feed())
        await self._sleep_until(phase.end_s, elapsed)

    async def _phase_search(self, *, username, session_id, engine, budget, keyword, phase, elapsed, allowed=None, **_):
        """2–10′ : un seul mot-clé, vidéos regardées en entier, ~1 like sur 3."""
        try:
            await self._record(session_id, username, "search", await engine.open_search(keyword))
            opened = await engine.open_first_result()
            await self._record(session_id, username, "search", opened)
        except UncalibratedPoint as e:
            await self._record(session_id, username, "search", f"SKIP — {e}")
            await self._sleep_until(phase.end_s, elapsed)
            return


        # Un like ne compte que si le cœur a réellement basculé. Deux ratés de
        # suite ne sont pas de la malchance : ils veulent dire qu'on n'est pas
        # sur une vidéo. La session #42 a scrollé huit minutes dans TikTok Shop
        # en journalisant neuf likes imaginaires ; on préfère désormais
        # abandonner la phase et le dire.
        missed = 0
        while elapsed() < phase.end_s and not self._stop_event.is_set():
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
                            await self._sleep_until(phase.end_s, elapsed)
                            return
                else:
                    missed = 0
                    budget.record_like()
                    await self._record(session_id, username, "like", detail)

            await self._record(session_id, username, "scroll", await engine.scroll_feed())
        await self._sleep_until(phase.end_s, elapsed)

    async def _phase_profiles(self, *, username, session_id, engine, budget, phase, elapsed, allowed=None, **_):
        """10–13′ : deux ou trois profils, 2–3 abonnements max, jamais d'affilée.

        Sautée tant que la montée en charge n'a pas débloqué la visite de
        profil : aux jours 1-4 le compte se contente de regarder le fil.
        """
        if allowed is not None and "visit_profile" not in allowed:
            await self._record(
                session_id, username, "visit_profile",
                "SKIP — visite de profil pas encore débloquée par la montée en charge",
            )
            await self._phase_fyp_entry(
                username=username, session_id=session_id, engine=engine,
                budget=budget, phase=phase, elapsed=elapsed, allowed=allowed,
            )
            return
        while (
            elapsed() < phase.end_s
            and not self._stop_event.is_set()
            and budget.profiles_remaining() > 0
        ):
            # Repartir du fil à chaque tour. `creator_avatar` n'existe que sur
            # une vidéo : après le premier profil on est resté sur une page de
            # profil, et le tap n'ouvrait plus rien de neuf.
            await engine.return_to_feed()
            for _ in range(random.randint(1, 4)):
                await engine.scroll_feed()

            try:
                await self._record(session_id, username, "visit_profile", await engine.open_creator_profile())
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
        await self._sleep_until(phase.end_s, elapsed)

    async def _phase_fyp_measure(self, *, username, session_id, engine, phase, elapsed, allowed=None, **_):
        """13–18′ : retour au FYP, 20 scrolls capturés pour comptage manuel."""
        detail = await engine.return_to_feed()
        if detail == "SKIP":
            await self._record(
                session_id, username, "fyp_measure",
                "SKIP — le clavier est resté ouvert, mesure abandonnée",
            )
            await self._sleep_until(phase.end_s, elapsed)
            return
        await self._record(session_id, username, "fyp_measure", detail)

        shots_dir = os.path.join(self.fyp_shots_dir, str(session_id))
        taken, distinct = await engine.measure_fyp(shots_dir)
        note = f"{taken} captures, {distinct} vidéos distinctes dans {shots_dir}"
        if distinct < protocol.FYP_MEASURE_SCROLLS // 2:
            note += " — fil bloqué, mesure peu fiable"
        await self._record(session_id, username, "fyp_measure",
                           note + " — comptage à saisir sur le dashboard")
        await self._sleep_until(phase.end_s, elapsed)

    async def _sleep_until(self, target_s: float, elapsed) -> None:
        """Tient la phase jusqu'à sa fin, sans dépasser sur la suivante."""
        while elapsed() < target_s and not self._stop_event.is_set():
            await asyncio.sleep(min(2.0, target_s - elapsed()))

    async def _record(self, session_id: int, username: str, action: str, detail: str) -> None:
        """Journalise une action déjà exécutée et la pousse au dashboard.

        Un refus n'entre jamais dans `action_logs` : ces lignes alimentent les
        plafonds 24 h, et compter un abonnement refusé comme un abonnement
        restreindrait la session du lendemain sur une action qui n'a pas eu
        lieu. Le refus reste visible au dashboard, en événement `refused`.
        """
        if detail == "SKIP" or detail.startswith("SKIP"):
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
        if detail == "SKIP":
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

    async def _set_error(self, username: str, error: str):
        with self.Session() as session:
            account = session.query(Account).filter_by(username=username).first()
            if account:
                account.status = "error"
                session.commit()
        await self._broadcast({
            "type": "error", "username": username,
            "data": error, "timestamp": datetime.datetime.now().isoformat(),
        })
