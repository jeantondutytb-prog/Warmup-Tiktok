import os
import tempfile
from app.config import load_settings, get_accounts, get_scoring_config


def test_load_settings():
    content = """
check_interval_hours: 4
db_url: "sqlite:///db/monitor.db"
port: 8001
accounts:
  - username: "emma.srpt"
    tiktok_handle: "@emma.srtp"
    role: "flagship"
  - username: "chloe.rtps"
    tiktok_handle: "@chloe.rtps"
    role: "secondary"
scoring:
  weights:
    follower_ratio: 0.15
    engagement_rate: 0.30
  thresholds:
    healthy: 70
    warning: 40
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(content)
        path = f.name
    try:
        settings = load_settings(path)
        assert settings["check_interval_hours"] == 4
        assert settings["port"] == 8001
    finally:
        os.unlink(path)


def test_get_accounts():
    settings = {
        "accounts": [
            {"username": "u1", "tiktok_handle": "@u1", "role": "flagship"},
            {"username": "u2", "tiktok_handle": "@u2", "role": "secondary"},
        ]
    }
    accounts = get_accounts(settings)
    assert len(accounts) == 2
    assert accounts[0]["username"] == "u1"


def test_get_accounts_empty():
    assert get_accounts({}) == []


def test_get_scoring_config():
    settings = {
        "scoring": {
            "weights": {"follower_ratio": 0.20},
            "thresholds": {"healthy": 75, "warning": 45},
        }
    }
    config = get_scoring_config(settings)
    assert config["weights"]["follower_ratio"] == 0.20
    assert config["thresholds"]["healthy"] == 75


def test_get_scoring_config_defaults():
    config = get_scoring_config({})
    assert "weights" in config
    assert "thresholds" in config
    assert config["thresholds"]["healthy"] == 70
