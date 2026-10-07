from __future__ import annotations
import asyncio
import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session as SASession
from app.models.models import Base, MonitoredAccount, HealthCheck
from app.core.cookie_manager import validate_cookies
from app.core.scraper import scrape_profile
from app.core.health_scorer import score_health
from app.config import get_accounts, get_scoring_config


class CheckOrchestrator:
    def __init__(self, db_url: str, settings: dict):
        self.engine = create_engine(db_url, connect_args={"check_same_thread": False})
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.settings = settings
        self.scoring_config = get_scoring_config(settings)
        self._subscribers: list[asyncio.Queue] = []
        self._init_accounts()

    def _init_accounts(self):
        accounts_cfg = get_accounts(self.settings)
        with self.Session() as db:
            for cfg in accounts_cfg:
                existing = db.query(MonitoredAccount).filter_by(username=cfg["username"]).first()
                if not existing:
                    account = MonitoredAccount(
                        username=cfg["username"],
                        tiktok_handle=cfg["tiktok_handle"],
                        role=cfg.get("role", "secondary"),
                    )
                    db.add(account)
            db.commit()

    def get_all_status(self) -> dict[str, dict]:
        result = {}
        with self.Session() as db:
            accounts = db.query(MonitoredAccount).filter_by(active=True).all()
            for acc in accounts:
                recent_checks = acc.checks[:10]
                result[acc.username] = {
                    "tiktok_handle": acc.tiktok_handle,
                    "role": acc.role,
                    "has_cookies": acc.get_cookies() is not None,
                    "last_check_at": acc.last_check_at.isoformat() if acc.last_check_at else None,
                    "last_score": acc.last_score,
                    "last_level": acc.last_level,
                    "history": [
                        {
                            "checked_at": c.checked_at.isoformat(),
                            "score": c.score,
                            "level": c.level,
                            "status": c.status,
                            "followers": c.followers,
                            "following": c.following,
                            "total_likes": c.total_likes,
                            "video_count": c.video_count,
                        }
                        for c in recent_checks
                    ],
                }
        return result

    def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=100)
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

    async def check_account(self, username: str) -> dict:
        with self.Session() as db:
            account = db.query(MonitoredAccount).filter_by(username=username).first()
            if not account:
                raise ValueError(f"Unknown account: {username}")

            check = HealthCheck(account_id=account.id, status="running")
            db.add(check)
            db.commit()
            db.refresh(check)
            check_id = check.id
            account_id = account.id
            handle = account.tiktok_handle
            cookies = account.get_cookies()

            previous_followers = None
            recent_scores = []
            for c in account.checks:
                if c.id != check_id and c.status == "completed":
                    if previous_followers is None and c.followers is not None:
                        previous_followers = c.followers
                    if c.score is not None:
                        recent_scores.append(c.score)
                    if len(recent_scores) >= 5:
                        break

        await self._broadcast({
            "type": "check_start",
            "username": username,
            "timestamp": datetime.datetime.utcnow().isoformat(),
        })

        if not validate_cookies(cookies):
            with self.Session() as db:
                check = db.query(HealthCheck).get(check_id)
                check.status = "failed"
                check.error_message = "No valid cookies"
                db.commit()
            await self._broadcast({
                "type": "check_error",
                "username": username,
                "data": "No valid cookies",
                "timestamp": datetime.datetime.utcnow().isoformat(),
            })
            return {"status": "failed", "error": "No valid cookies"}

        try:
            profile = await scrape_profile(handle, cookies)
        except Exception as e:
            with self.Session() as db:
                check = db.query(HealthCheck).get(check_id)
                check.status = "failed"
                check.error_message = str(e)
                db.commit()
            await self._broadcast({
                "type": "check_error",
                "username": username,
                "data": str(e),
                "timestamp": datetime.datetime.utcnow().isoformat(),
            })
            return {"status": "failed", "error": str(e)}

        weights = self.scoring_config.get("weights")
        thresholds = self.scoring_config.get("thresholds")
        result = score_health(
            followers=profile["followers"],
            following=profile["following"],
            total_likes=profile["total_likes"],
            video_count=profile["video_count"],
            previous_followers=previous_followers,
            recent_scores=recent_scores,
            weights=weights,
            thresholds=thresholds,
        )

        with self.Session() as db:
            check = db.query(HealthCheck).get(check_id)
            check.status = "completed"
            check.followers = profile["followers"]
            check.following = profile["following"]
            check.total_likes = profile["total_likes"]
            check.video_count = profile["video_count"]
            check.bio = profile.get("bio", "")
            check.verified = profile.get("verified", False)
            check.score = result["score"]
            check.level = result["level"]
            check.set_metrics(result["breakdown"])

            account = db.query(MonitoredAccount).get(account_id)
            account.last_check_at = datetime.datetime.utcnow()
            account.last_score = result["score"]
            account.last_level = result["level"]
            db.commit()

        await self._broadcast({
            "type": "check_done",
            "username": username,
            "score": result["score"],
            "level": result["level"],
            "timestamp": datetime.datetime.utcnow().isoformat(),
        })

        return {"status": "completed", **result}

    async def check_all(self) -> dict[str, dict]:
        results = {}
        with self.Session() as db:
            accounts = db.query(MonitoredAccount).filter_by(active=True).all()
            usernames = [a.username for a in accounts]
        for username in usernames:
            results[username] = await self.check_account(username)
        return results
