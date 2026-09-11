import os
import tempfile
from app.config import load_accounts, load_devices, load_comments


def test_load_accounts():
    yaml_content = """
accounts:
  - username: "user1"
    password: "pass1"
    device_profile: "pixel_6"
    comment_style: "casual"
  - username: "user2"
    password: "pass2"
    device_profile: "samsung_s21"
    comment_style: "emoji_heavy"
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml_content)
        path = f.name
    try:
        accounts = load_accounts(path)
        assert len(accounts) == 2
        assert accounts[0]["username"] == "user1"
        assert accounts[1]["device_profile"] == "samsung_s21"
    finally:
        os.unlink(path)


def test_load_devices():
    yaml_content = """
devices:
  pixel_6:
    model: "Pixel 6"
    resolution: "1080x2400"
    android_version: "13"
  samsung_s21:
    model: "Samsung Galaxy S21"
    resolution: "1080x2400"
    android_version: "12"
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
        f.write(yaml_content)
        path = f.name
    try:
        devices = load_devices(path)
        assert "pixel_6" in devices
        assert devices["pixel_6"]["model"] == "Pixel 6"
    finally:
        os.unlink(path)


def test_load_comments():
    content = """# casual
Super cool!
J'adore cette vidéo
Trop bien 🔥

# emoji_heavy
🔥🔥🔥
❤️❤️
😂😂😂

# questions
Comment tu fais ça ?
C'est quoi la musique ?
"""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False) as f:
        f.write(content)
        path = f.name
    try:
        comments = load_comments(path)
        assert "casual" in comments
        assert len(comments["casual"]) == 3
        assert "emoji_heavy" in comments
        assert comments["questions"][0] == "Comment tu fais ça ?"
    finally:
        os.unlink(path)
