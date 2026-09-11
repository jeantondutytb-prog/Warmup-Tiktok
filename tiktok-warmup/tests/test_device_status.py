from unittest.mock import patch

from app.core.device_status import get_device_status


def test_device_status_not_ready_without_iphone():
    with patch("app.core.device_status._detect_iphone") as mock_iphone:
        mock_iphone.return_value = {
            "connected": False,
            "udid": None,
            "name": None,
            "message": "Aucun iPhone détecté",
        }
        with patch("app.core.device_status._wda_ready") as mock_wda:
            mock_wda.return_value = (False, "WDA inaccessible")
            status = get_device_status("http://127.0.0.1:8100")
    assert status["ready"] is False
    assert status["iphone"]["connected"] is False
    assert status["wda"]["ready"] is False


def test_device_status_ready_when_both_ok():
    with patch("app.core.device_status._detect_iphone") as mock_iphone:
        mock_iphone.return_value = {
            "connected": True,
            "udid": "abc",
            "name": "iPhone XS",
            "message": "iPhone XS connecté",
        }
        with patch("app.core.device_status._wda_ready") as mock_wda:
            mock_wda.return_value = (True, "WebDriverAgent prêt")
            status = get_device_status("http://192.168.1.61:8100")
    assert status["ready"] is True
    assert status["wda"]["url"] == "http://192.168.1.61:8100"
