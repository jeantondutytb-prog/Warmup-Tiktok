import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class Settings:
    client_key: str
    client_secret: str
    redirect_uri: str
    app_base_url: str
    demo_mode: bool
    db_path: str

    @property
    def oauth_configured(self) -> bool:
        return bool(self.client_key and self.client_secret)

    @property
    def oauth_scopes(self) -> str:
        return "user.info.basic,user.info.stats,video.list"


def get_settings() -> Settings:
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    db_dir = os.path.join(base_dir, "data")
    os.makedirs(db_dir, exist_ok=True)
    demo = os.getenv("DEMO_MODE", "0").strip().lower() in {"1", "true", "yes"}
    client_key = os.getenv("TIKTOK_CLIENT_KEY", "").strip()
    client_secret = os.getenv("TIKTOK_CLIENT_SECRET", "").strip()
    placeholders = {"", "your_client_key", "your_client_secret", "changeme"}
    if client_key in placeholders:
        client_key = ""
    if client_secret in placeholders:
        client_secret = ""
    return Settings(
        client_key=client_key,
        client_secret=client_secret,
        redirect_uri=os.getenv(
            "TIKTOK_REDIRECT_URI", "http://127.0.0.1:8080/auth/callback"
        ).strip(),
        app_base_url=os.getenv("APP_BASE_URL", "http://127.0.0.1:8080").strip().rstrip("/"),
        demo_mode=demo,
        db_path=os.path.join(db_dir, "studio.db"),
    )
