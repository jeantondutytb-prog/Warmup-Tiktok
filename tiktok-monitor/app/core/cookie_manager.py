from __future__ import annotations
from sqlalchemy.orm import Session as SASession
from app.models.models import MonitoredAccount


def store_cookies(db: SASession, username: str, cookies: dict) -> bool:
    account = db.query(MonitoredAccount).filter_by(username=username).first()
    if not account:
        return False
    account.set_cookies(cookies)
    db.commit()
    return True


def get_cookies(db: SASession, username: str) -> dict | None:
    account = db.query(MonitoredAccount).filter_by(username=username).first()
    if not account:
        return None
    return account.get_cookies()


def validate_cookies(cookies: dict | None) -> bool:
    if not cookies:
        return False
    required = {"sessionid"}
    return required.issubset(cookies.keys())


def cookies_to_header(cookies: dict) -> str:
    return "; ".join(f"{k}={v}" for k, v in cookies.items())
