import datetime

from sqlalchemy import Column, DateTime, Integer, String, Text, create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker


class Base(DeclarativeBase):
    pass


class ConnectedAccount(Base):
    __tablename__ = "connected_accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    open_id = Column(String, nullable=False, unique=True)
    display_name = Column(String, nullable=False, default="")
    avatar_url = Column(String, nullable=False, default="")
    access_token = Column(Text, nullable=False, default="")
    refresh_token = Column(Text, nullable=False, default="")
    token_expires_at = Column(DateTime, nullable=True)
    refresh_expires_at = Column(DateTime, nullable=True)
    follower_count = Column(Integer, nullable=False, default=0)
    following_count = Column(Integer, nullable=False, default=0)
    likes_count = Column(Integer, nullable=False, default=0)
    video_count = Column(Integer, nullable=False, default=0)
    total_views = Column(Integer, nullable=False, default=0)
    total_video_likes = Column(Integer, nullable=False, default=0)
    total_comments = Column(Integer, nullable=False, default=0)
    total_shares = Column(Integer, nullable=False, default=0)
    last_synced_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, nullable=False, default=datetime.datetime.utcnow)


def build_session_factory(db_path: str):
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)
