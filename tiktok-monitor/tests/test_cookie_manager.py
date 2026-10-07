from app.core.cookie_manager import store_cookies, get_cookies, validate_cookies, cookies_to_header


def test_store_and_get_cookies(db_session, sample_account):
    ok = store_cookies(db_session, "emma.srpt", {"sessionid": "abc", "tt_csrf_token": "xyz"})
    assert ok is True
    cookies = get_cookies(db_session, "emma.srpt")
    assert cookies["sessionid"] == "abc"


def test_store_cookies_unknown_account(db_session):
    ok = store_cookies(db_session, "nonexistent", {"sessionid": "abc"})
    assert ok is False


def test_get_cookies_no_account(db_session):
    assert get_cookies(db_session, "nonexistent") is None


def test_get_cookies_none_set(db_session, sample_account):
    assert get_cookies(db_session, "emma.srpt") is None


def test_validate_cookies_valid():
    assert validate_cookies({"sessionid": "abc123"}) is True


def test_validate_cookies_missing_sessionid():
    assert validate_cookies({"tt_csrf_token": "xyz"}) is False


def test_validate_cookies_none():
    assert validate_cookies(None) is False


def test_validate_cookies_empty():
    assert validate_cookies({}) is False


def test_cookies_to_header():
    header = cookies_to_header({"sessionid": "abc", "tt_csrf_token": "xyz"})
    assert "sessionid=abc" in header
    assert "tt_csrf_token=xyz" in header
    assert "; " in header
