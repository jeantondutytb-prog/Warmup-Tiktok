from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.models.models import Base

_engine = None
_SessionLocal = None


def init_db(db_url: str = "sqlite:///db/warmup.db") -> None:
    global _engine, _SessionLocal
    _engine = create_engine(db_url, connect_args={"check_same_thread": False})
    _SessionLocal = sessionmaker(bind=_engine)
    Base.metadata.create_all(_engine)


def get_db():
    session = _SessionLocal()
    try:
        yield session
    finally:
        session.close()
