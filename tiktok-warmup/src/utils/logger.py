import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from rich.console import Console
from rich.logging import RichHandler

console = Console()


def setup_logger(name: str = "tiktok-warmup", log_dir: Path | None = None) -> logging.Logger:
    logger = logging.getLogger(name)
    if logger.handlers:
        return logger

    logger.setLevel(logging.DEBUG)
    handler = RichHandler(console=console, rich_tracebacks=True, show_time=True)
    handler.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(handler)

    if log_dir:
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_dir / "session.log")
        file_handler.setFormatter(
            logging.Formatter("%(asctime)s [%(levelname)s] %(message)s")
        )
        logger.addHandler(file_handler)

    return logger


class SessionStats:
    """Collecte les statistiques d'une session de warmup."""

    def __init__(self, profile: str):
        self.profile = profile
        self.started_at = datetime.now(timezone.utc)
        self.videos_watched = 0
        self.likes = 0
        self.follows = 0
        self.comments = 0
        self.profile_visits = 0
        self.scroll_backs = 0
        self.pauses = 0
        self.total_watch_seconds = 0.0
        self.actions: list[dict] = []

    def record(self, action: str, **details) -> None:
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            **details,
        }
        self.actions.append(entry)

        match action:
            case "watch":
                self.videos_watched += 1
                self.total_watch_seconds += details.get("duration", 0)
            case "like":
                self.likes += 1
            case "follow":
                self.follows += 1
            case "comment":
                self.comments += 1
            case "profile_visit":
                self.profile_visits += 1
            case "scroll_back":
                self.scroll_backs += 1
            case "pause":
                self.pauses += 1

    def summary(self) -> dict:
        elapsed = (datetime.now(timezone.utc) - self.started_at).total_seconds()
        return {
            "profile": self.profile,
            "duration_seconds": round(elapsed, 1),
            "videos_watched": self.videos_watched,
            "likes": self.likes,
            "follows": self.follows,
            "comments": self.comments,
            "profile_visits": self.profile_visits,
            "scroll_backs": self.scroll_backs,
            "pauses": self.pauses,
            "total_watch_seconds": round(self.total_watch_seconds, 1),
            "avg_watch_seconds": round(
                self.total_watch_seconds / max(self.videos_watched, 1), 1
            ),
        }

    def save(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        data = {**self.summary(), "actions": self.actions}
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
