import hashlib
import secrets
import string

_VERIFIER_CHARS = string.ascii_letters + string.digits + "-._~"


def generate_code_verifier(length: int = 64) -> str:
    if length < 43 or length > 128:
        raise ValueError("code_verifier must be between 43 and 128 characters")
    return "".join(secrets.choice(_VERIFIER_CHARS) for _ in range(length))


def generate_code_challenge(code_verifier: str) -> str:
    """TikTok Desktop PKCE : HEX(SHA256(verifier)), pas base64url."""
    digest = hashlib.sha256(code_verifier.encode("utf-8")).digest()
    return digest.hex()
