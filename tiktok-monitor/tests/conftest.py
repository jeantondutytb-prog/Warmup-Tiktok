import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session as SASession
from app.models.models import Base, MonitoredAccount


@pytest.fixture
def db_engine():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


@pytest.fixture
def db_session(db_engine):
    Session = sessionmaker(bind=db_engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def sample_account(db_session):
    account = MonitoredAccount(
        username="emma.srpt",
        tiktok_handle="@emma.srtp",
        role="flagship",
    )
    db_session.add(account)
    db_session.commit()
    db_session.refresh(account)
    return account
