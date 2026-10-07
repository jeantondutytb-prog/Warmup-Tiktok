import json
import pytest
import httpx
from unittest.mock import AsyncMock, patch
from app.core.scraper import scrape_profile, build_headers, _parse_profile_page


def test_build_headers():
    headers = build_headers({"sessionid": "abc"})
    assert "Cookie" in headers
    assert "sessionid=abc" in headers["Cookie"]
    assert "User-Agent" in headers


def test_parse_profile_universal_data():
    user_data = {
        "__DEFAULT_SCOPE__": {
            "webapp.user-detail": {
                "userInfo": {
                    "user": {
                        "signature": "Hello world",
                        "verified": True,
                        "nickname": "Emma",
                    },
                    "stats": {
                        "followerCount": 1500,
                        "followingCount": 200,
                        "heartCount": 45000,
                        "videoCount": 25,
                    },
                }
            }
        }
    }
    html = f'<html><script id="__UNIVERSAL_DATA_FOR_REHYDRATION__">{json.dumps(user_data)}</script></html>'
    result = _parse_profile_page(html, "emma")
    assert result["followers"] == 1500
    assert result["following"] == 200
    assert result["total_likes"] == 45000
    assert result["video_count"] == 25
    assert result["bio"] == "Hello world"
    assert result["verified"] is True


def test_parse_profile_sigi_state():
    user_data = {
        "UserModule": {
            "users": {
                "emma": {
                    "signature": "Bio text",
                    "verified": False,
                    "nickname": "Em",
                }
            },
            "stats": {
                "emma": {
                    "followerCount": 800,
                    "followingCount": 100,
                    "heartCount": 20000,
                    "videoCount": 15,
                }
            },
        }
    }
    html = f'<html><script id="SIGI_STATE">{json.dumps(user_data)}</script></html>'
    result = _parse_profile_page(html, "emma")
    assert result["followers"] == 800
    assert result["video_count"] == 15


def test_parse_profile_no_data():
    result = _parse_profile_page("<html><body>Nothing</body></html>", "emma")
    assert result["followers"] == 0
    assert result["handle"] == "emma"


@pytest.mark.asyncio
async def test_scrape_profile_success():
    user_data = {
        "__DEFAULT_SCOPE__": {
            "webapp.user-detail": {
                "userInfo": {
                    "user": {"signature": "Hi", "verified": False, "nickname": "E"},
                    "stats": {"followerCount": 500, "followingCount": 50, "heartCount": 10000, "videoCount": 10},
                }
            }
        }
    }
    html = f'<html><script id="__UNIVERSAL_DATA_FOR_REHYDRATION__">{json.dumps(user_data)}</script></html>'

    mock_response = AsyncMock()
    mock_response.status_code = 200
    mock_response.text = html
    mock_response.raise_for_status = lambda: None

    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(return_value=mock_response)

    result = await scrape_profile("@emma", {"sessionid": "abc"}, client=mock_client)
    assert result["followers"] == 500
    assert result["video_count"] == 10


@pytest.mark.asyncio
async def test_scrape_profile_error():
    mock_client = AsyncMock(spec=httpx.AsyncClient)
    mock_client.get = AsyncMock(side_effect=httpx.HTTPError("Connection refused"))

    with pytest.raises(httpx.HTTPError):
        await scrape_profile("@emma", {"sessionid": "abc"}, client=mock_client)
