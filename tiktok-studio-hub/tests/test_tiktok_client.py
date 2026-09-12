import json

import httpx

from app.tiktok_client import TikTokClient


def test_token_response_accepts_error_code_ok():
    client = TikTokClient("key", "secret")
    resp = httpx.Response(
        200,
        json={
            "data": {
                "access_token": "act.test",
                "open_id": "oid",
                "expires_in": 86400,
            },
            "error": {"code": "ok", "message": ""},
        },
    )
    data = client._parse_token_response(resp)
    assert data["access_token"] == "act.test"
    assert data["open_id"] == "oid"


def test_token_response_flat_payload():
    client = TikTokClient("key", "secret")
    resp = httpx.Response(
        200,
        json={
            "access_token": "act.flat",
            "refresh_token": "rft.flat",
            "error": {"code": "ok", "message": ""},
        },
    )
    data = client._parse_token_response(resp)
    assert data["access_token"] == "act.flat"


def test_token_response_rejects_api_error():
    client = TikTokClient("key", "secret")
    resp = httpx.Response(
        200,
        json={"error": {"code": "invalid_client", "message": "bad key"}},
    )
    try:
        client._parse_token_response(resp)
        assert False, "expected TikTokApiError"
    except Exception as exc:
        assert "bad key" in str(exc)
