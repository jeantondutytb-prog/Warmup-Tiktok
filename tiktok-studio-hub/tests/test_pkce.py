from app.pkce import generate_code_challenge, generate_code_verifier
from app.tiktok_client import TikTokClient


def test_code_challenge_is_hex_sha256():
    verifier = "abcdefghijklmnopqrstuvwxyz0123456789ABCDEFG-_~abc"
    challenge = generate_code_challenge(verifier)
    assert len(challenge) == 64
    assert challenge == challenge.lower()
    assert all(c in "0123456789abcdef" for c in challenge)


def test_authorize_url_includes_pkce_params():
    client = TikTokClient("test_key", "secret")
    verifier = generate_code_verifier()
    challenge = generate_code_challenge(verifier)
    url = client.authorize_url(
        "http://127.0.0.1:8080/auth/callback",
        "state123",
        "user.info.basic,video.list",
        code_challenge=challenge,
    )
    assert "code_challenge=" in url
    assert "code_challenge_method=S256" in url
    assert challenge in url
