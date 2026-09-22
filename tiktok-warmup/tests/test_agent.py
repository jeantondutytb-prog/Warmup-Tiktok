from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agent.bridge import handle_job
from agent.client import ControlPlane
from agent.wda import build_xcodebuild_cmd, parse_server_url, preferred_udid


@pytest.mark.parametrize(
    "line, expected",
    [
        (
            "ServerURLHere->http://192.168.1.61:8100<-ServerURLHere",
            "http://192.168.1.61:8100",
        ),
        ("ServerURLHere->http://169.254.140.1:8100", "http://169.254.140.1:8100"),
        ("nothing useful", None),
        ("", None),
    ],
)
def test_parse_server_url(line, expected):
    assert parse_server_url(line) == expected


def test_xcodebuild_cmd_uses_udid_and_provisioning():
    cmd = build_xcodebuild_cmd("00008020-000D0CE43A99002E")
    assert cmd[0] == "xcodebuild"
    assert "test-without-building" in cmd
    assert "-allowProvisioningUpdates" in cmd
    assert "id=00008020-000D0CE43A99002E" in cmd
    assert any(part.startswith("DEVELOPMENT_TEAM=") for part in cmd)


def test_xcodebuild_rebuild_switches_action():
    cmd = build_xcodebuild_cmd("UDID", rebuild=True)
    assert "build-for-testing" in cmd
    assert "test-without-building" not in cmd


def test_preferred_udid_prefers_detected(monkeypatch):
    monkeypatch.setenv("DEVICE_UDID", "env-udid")
    with patch("agent.wda.list_iphone_udids", return_value=["usb-udid"]):
        assert preferred_udid() == "usb-udid"


def test_preferred_udid_keeps_env_if_connected(monkeypatch):
    monkeypatch.setenv("DEVICE_UDID", "env-udid")
    with patch("agent.wda.list_iphone_udids", return_value=["other", "env-udid"]):
        assert preferred_udid() == "env-udid"


def test_preferred_udid_none_when_unplugged(monkeypatch):
    monkeypatch.delenv("DEVICE_UDID", raising=False)
    with patch("agent.wda.list_iphone_udids", return_value=[]):
        assert preferred_udid() is None


def test_control_plane_requires_url_and_token(monkeypatch):
    monkeypatch.delenv("WARMUP_URL", raising=False)
    monkeypatch.delenv("AGENT_TOKEN", raising=False)
    with pytest.raises(RuntimeError, match="WARMUP_URL"):
        ControlPlane(base_url="", token="x")
    with pytest.raises(RuntimeError, match="AGENT_TOKEN"):
        ControlPlane(base_url="https://example.com", token="")


@pytest.mark.asyncio
async def test_handle_job_dispatches():
    orch = MagicMock()
    orch.start_account = AsyncMock()
    orch.start_all = AsyncMock()
    orch.stop_all = AsyncMock()
    orch.record_fyp_count.return_value = {"verdict": "warming"}
    orch.advance_protocol_day.return_value = {"protocol_day": 4}

    await handle_job(orch, {"type": "start", "username": "emma.srpt", "force": True})
    orch.start_account.assert_awaited_once_with("emma.srpt", force=True)

    await handle_job(orch, {"type": "start-all"})
    orch.start_all.assert_awaited_once()

    await handle_job(orch, {"type": "stop-all"})
    orch.stop_all.assert_awaited_once()

    await handle_job(orch, {"type": "fyp", "sessionId": 12, "count": 3})
    orch.record_fyp_count.assert_called_once_with(12, 3)

    await handle_job(orch, {"type": "protocol-day", "username": "emma.srpt", "day": 4})
    orch.advance_protocol_day.assert_called_once_with("emma.srpt", 4)


@pytest.mark.asyncio
async def test_handle_job_unknown():
    with pytest.raises(ValueError, match="inconnu"):
        await handle_job(MagicMock(), {"type": "explode"})
