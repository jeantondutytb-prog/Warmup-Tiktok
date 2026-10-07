import yaml


def load_settings(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def get_accounts(settings: dict) -> list[dict]:
    return settings.get("accounts", [])


def get_scoring_config(settings: dict) -> dict:
    return settings.get("scoring", {
        "weights": {
            "follower_ratio": 0.15,
            "engagement_rate": 0.30,
            "video_count": 0.10,
            "growth_trend": 0.25,
            "consistency": 0.20,
        },
        "thresholds": {"healthy": 70, "warning": 40},
    })
