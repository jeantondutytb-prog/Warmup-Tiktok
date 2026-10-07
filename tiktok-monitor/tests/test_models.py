import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import Session as SASession
from app.models.models import Base, MonitoredAccount, HealthCheck
from app.models.database import init_db


def make_engine():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


def test_account_creation():
    engine = make_engine()
    with SASession(engine) as session:
        account = MonitoredAccount(
            username="emma.srpt",
            tiktok_handle="@emma.srtp",
            role="flagship",
        )
        session.add(account)
        session.commit()
        session.refresh(account)
        assert account.id is not None
        assert account.username == "emma.srpt"
        assert account.tiktok_handle == "@emma.srtp"
        assert account.active is True
        assert account.last_score is None
        assert isinstance(account.created_at, datetime.datetime)


def test_account_cookies():
    engine = make_engine()
    with SASession(engine) as session:
        account = MonitoredAccount(
            username="test_user",
            tiktok_handle="@test_user",
        )
        session.add(account)
        session.commit()

        account.set_cookies({"sessionid": "abc123", "tt_csrf_token": "xyz"})
        session.commit()
        session.refresh(account)

        cookies = account.get_cookies()
        assert cookies["sessionid"] == "abc123"
        assert cookies["tt_csrf_token"] == "xyz"


def test_account_no_cookies():
    engine = make_engine()
    with SASession(engine) as session:
        account = MonitoredAccount(username="u1", tiktok_handle="@u1")
        session.add(account)
        session.commit()
        assert account.get_cookies() is None


def test_health_check_creation():
    engine = make_engine()
    with SASession(engine) as session:
        account = MonitoredAccount(username="u1", tiktok_handle="@u1")
        session.add(account)
        session.commit()
        session.refresh(account)

        check = HealthCheck(
            account_id=account.id,
            followers=1500,
            following=200,
            total_likes=45000,
            video_count=25,
            score=78.5,
            level="healthy",
            status="completed",
        )
        session.add(check)
        session.commit()
        session.refresh(check)

        assert check.id is not None
        assert check.followers == 1500
        assert check.score == 78.5
        assert check.level == "healthy"
        assert check.status == "completed"
        assert check.account_id == account.id


def test_health_check_metrics_json():
    engine = make_engine()
    with SASession(engine) as session:
        account = MonitoredAccount(username="u1", tiktok_handle="@u1")
        session.add(account)
        session.commit()
        session.refresh(account)

        check = HealthCheck(account_id=account.id, status="completed")
        check.set_metrics({"engagement_rate": 0.03, "follower_ratio": 7.5})
        session.add(check)
        session.commit()
        session.refresh(check)

        metrics = check.get_metrics()
        assert metrics["engagement_rate"] == 0.03
        assert metrics["follower_ratio"] == 7.5


def test_health_check_relationship():
    engine = make_engine()
    with SASession(engine) as session:
        account = MonitoredAccount(username="u1", tiktok_handle="@u1")
        session.add(account)
        session.commit()
        session.refresh(account)

        check = HealthCheck(account_id=account.id, status="completed", score=80.0)
        session.add(check)
        session.commit()

        session.refresh(account)
        assert len(account.checks) == 1
        assert account.checks[0].score == 80.0


def test_init_db_creates_tables():
    init_db("sqlite:///:memory:")
