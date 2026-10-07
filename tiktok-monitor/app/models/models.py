import datetime
import json
from sqlalchemy import Column, Integer, String, DateTime, Float, Boolean, Text, ForeignKey
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class MonitoredAccount(Base):
    __tablename__ = "monitored_accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, nullable=False, unique=True)
    tiktok_handle = Column(String, nullable=False)
    role = Column(String, nullable=False, default="secondary")
    cookies_json = Column(Text, nullable=True)
    last_check_at = Column(DateTime, nullable=True)
    last_score = Column(Float, nullable=True)
    last_level = Column(String, nullable=True)
    active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False, default=datetime.datetime.utcnow)

    checks = relationship("HealthCheck", back_populates="account", order_by="HealthCheck.checked_at.desc()")

    def set_cookies(self, cookies: dict) -> None:
        self.cookies_json = json.dumps(cookies)

    def get_cookies(self) -> dict | None:
        if self.cookies_json:
            return json.loads(self.cookies_json)
        return None


class HealthCheck(Base):
    __tablename__ = "health_checks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey("monitored_accounts.id"), nullable=False)
    checked_at = Column(DateTime, nullable=False, default=datetime.datetime.utcnow)
    score = Column(Float, nullable=True)
    level = Column(String, nullable=True)
    status = Column(String, nullable=False, default="pending")
    error_message = Column(String, nullable=True)
    followers = Column(Integer, nullable=True)
    following = Column(Integer, nullable=True)
    total_likes = Column(Integer, nullable=True)
    video_count = Column(Integer, nullable=True)
    bio = Column(String, nullable=True)
    verified = Column(Boolean, nullable=True)
    metrics_json = Column(Text, nullable=True)

    account = relationship("MonitoredAccount", back_populates="checks")

    def set_metrics(self, metrics: dict) -> None:
        self.metrics_json = json.dumps(metrics)

    def get_metrics(self) -> dict | None:
        if self.metrics_json:
            return json.loads(self.metrics_json)
        return None
