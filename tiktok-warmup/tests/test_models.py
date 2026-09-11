import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import Session as SASession
from app.models.models import Base, Account, WarmupSession, ActionLog
from app.models.database import init_db, get_db


def make_engine():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


def test_account_creation():
    engine = make_engine()
    with SASession(engine) as session:
        account = Account(username="test_user", device_profile="pixel_6", comment_style="casual")
        session.add(account)
        session.commit()
        session.refresh(account)
        assert account.id is not None
        assert account.username == "test_user"
        assert account.ramp_up_day == 1
        assert account.status == "idle"
        assert isinstance(account.created_at, datetime.datetime)


def test_session_and_action_log():
    engine = make_engine()
    with SASession(engine) as session:
        account = Account(username="u1", device_profile="pixel_6", comment_style="casual")
        session.add(account)
        session.commit()
        session.refresh(account)

        ws = WarmupSession(account_id=account.id, started_at=datetime.datetime.now())
        session.add(ws)
        session.commit()
        session.refresh(ws)

        log = ActionLog(session_id=ws.id, action_type="like", detail="liked video by @creator")
        session.add(log)
        session.commit()
        session.refresh(log)

        assert log.action_type == "like"
        assert log.session_id == ws.id


def test_init_db_creates_tables():
    init_db("sqlite:///:memory:")
