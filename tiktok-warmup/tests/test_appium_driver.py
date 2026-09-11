import json
from contextlib import contextmanager
from unittest.mock import MagicMock, patch

import pytest

from app.core.appium_driver import AppiumDriverManager, WDADriver


@contextmanager
def _noop():
    yield


def _http_response(payload: dict):
    """Un faux objet de réponse urlopen, utilisable comme context manager."""
    response = MagicMock()
    response.read.return_value = json.dumps(payload).encode()
    response.__enter__ = lambda self: self
    response.__exit__ = lambda self, *a: False
    return response


def test_create_session_opens_a_wda_session_and_launches_tiktok():
    """create_session parle à WebDriverAgent en direct, plus à Appium.

    Le pilote ne passe plus par `webdriver.Remote` : il ouvre une session WDA
    sur le lien USB et pilote l'iPhone en HTTP brut.
    """
    manager = AppiumDriverManager(appium_url="http://localhost:4723")

    responses = [
        _http_response({"value": {"sessionId": "sid-123"}}),  # POST /session
        _http_response({"value": {}}),                        # POST appium/settings
    ]

    with (
        patch.object(manager, "_ensure_wda_running"),
        patch("app.core.appium_driver.urllib.request.urlopen", side_effect=responses) as urlopen,
        patch.object(WDADriver, "get_window_size", return_value={"width": 375, "height": 812}),
        patch.object(WDADriver, "activate_app") as activate,
        patch("app.core.appium_driver.time.sleep"),
    ):
        driver = manager.create_session({}, account_name="compte1")

    assert isinstance(driver, WDADriver)
    assert driver.session_id == "sid-123"
    # L'app lancée est bien TikTok.
    activate.assert_called_once_with("com.zhiliaoapp.musically")

    created = urlopen.call_args_list[0][0][0]
    assert created.full_url.endswith("/session")
    assert json.loads(created.data)["capabilities"]["alwaysMatch"]["shouldWaitForQuiescence"] is False


def test_create_session_raises_when_wda_returns_no_session_id():
    manager = AppiumDriverManager()
    with (
        patch.object(manager, "_ensure_wda_running"),
        patch("app.core.appium_driver.urllib.request.urlopen",
              return_value=_http_response({"value": {}})),
    ):
        with pytest.raises(RuntimeError, match="session creation failed"):
            manager.create_session({}, "compte1")


def test_create_session_raises_if_no_iphone():
    manager = AppiumDriverManager()
    with patch.object(manager, "_get_iphone_udid", return_value=None):
        try:
            manager.create_session({}, "compte1")
            assert False, "Should have raised"
        except RuntimeError as e:
            assert "iPhone not detected" in str(e)


def test_close_session_quits_driver():
    manager = AppiumDriverManager()
    mock_driver = MagicMock()
    manager.close_session(mock_driver)
    mock_driver.quit.assert_called_once()
