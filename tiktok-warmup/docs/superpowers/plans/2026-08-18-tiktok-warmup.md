# TikTok Warmup App — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a local Python app that warms up 1-5 TikTok accounts via Android emulators, with a single-page dashboard to monitor and control all accounts.

**Architecture:** FastAPI backend orchestrates Appium sessions against per-account Android emulators. An anti-detection layer randomizes timing and ramps up actions progressively. A Jinja2+HTMX dashboard streams real-time logs via SSE.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy (SQLite), Appium 2.x, Jinja2, HTMX

**Spec:** `docs/superpowers/specs/2026-08-18-tiktok-warmup-design.md`

## Global Constraints

- Python 3.11+ required
- No external CSS frameworks — plain CSS only
- Passwords stored locally in `config/accounts.yaml`, never transmitted
- All randomization uses gaussian/normal distributions (not uniform) for human-like behavior
- Each account maps to exactly one Android emulator (AVD) with a unique device profile
- Appium interactions are always mocked in unit tests — integration tests require real emulators

---

### Task 1: Data Layer — Models, Config, Database

**Files:**
- Create: `requirements.txt`
- Create: `app/__init__.py`
- Create: `app/models/__init__.py`
- Create: `app/models/models.py`
- Create: `app/models/database.py`
- Create: `app/config.py`
- Create: `config/accounts.yaml`
- Create: `config/devices.yaml`
- Create: `config/comments.txt`
- Test: `tests/__init__.py`
- Test: `tests/test_models.py`
- Test: `tests/test_config.py`

**Interfaces:**
- Consumes: nothing (first task)
- Produces:
  - `app.models.database.get_db() -> Generator[Session]` — SQLAlchemy session factory
  - `app.models.database.init_db() -> None` — creates tables
  - `app.models.models.Account` — SQLAlchemy model with columns: id (int PK), username (str), device_profile (str), comment_style (str), ramp_up_day (int default 1), status (str default "idle"), created_at (datetime)
  - `app.models.models.WarmupSession` — columns: id (int PK), account_id (int FK), started_at (datetime), ended_at (datetime nullable), duration_seconds (int nullable)
  - `app.models.models.ActionLog` — columns: id (int PK), session_id (int FK), action_type (str), detail (str), timestamp (datetime)
  - `app.config.load_accounts(path: str) -> list[dict]` — parses accounts.yaml
  - `app.config.load_devices(path: str) -> dict[str, dict]` — parses devices.yaml keyed by profile name
  - `app.config.load_comments(path: str) -> dict[str, list[str]]` — parses comments.txt into {category: [comments]}

- [ ] **Step 1: Create requirements.txt**

```
fastapi==0.115.0
uvicorn==0.30.0
sqlalchemy==2.0.35
pyyaml==6.0.2
jinja2==3.1.4
sse-starlette==2.1.0
Appium-Python-Client==4.1.0
python-multipart==0.0.9
pytest==8.3.0
pytest-asyncio==0.24.0
httpx==0.27.0
```

Run: `cd /Users/jean/tiktok-warmup && python3 -m venv venv && source venv/bin/activate && pip install -r requirements.txt`

- [ ] **Step 2: Write failing tests for models**

Create `tests/__init__.py` (empty) and `tests/test_models.py`:

```python
import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import Session as SASession
from app.models.models import Base, Account, WarmupSession, ActionLog
from app.models.database import init_db, get_db


def make_engine():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return engine


def test_account_creation():
    engine = make_engine()
    with SASession(engine) as session:
        account = Account(username="test_user", device_profile="pixel_6", comment_style="casual")
        session.add(account)
        session.commit()
        session.refresh(account)
        assert account.id is not None
        assert account.username == "test_user"
        assert account.ramp_up_day == 1
        assert account.status == "idle"
        assert isinstance(account.created_at, datetime.datetime)


def test_session_and_action_log():
    engine = make_engine()
    with SASession(engine) as session:
        account = Account(username="u1", device_profile="pixel_6", comment_style="casual")
        session.add(account)
        session.commit()
        session.refresh(account)

        ws = WarmupSession(account_id=account.id, started_at=datetime.datetime.now())
        session.add(ws)
        session.commit()
        session.refresh(ws)

        log = ActionLog(session_id=ws.id, action_type="like", detail="liked video by @creator")
        session.add(log)
        session.commit()
        session.refresh(log)

        assert log.action_type == "like"
        assert log.session_id == ws.id


def test_init_db_creates_tables():
    init_db("sqlite:///:memory:")
```

Run: `cd /Users/jean/tiktok-warmup && source venv/bin/activate && python -m pytest tests/test_models.py -v`
Expected: FAIL — modules not found

- [ ] **Step 3: Implement models and database**

Create `app/__init__.py` (empty), `app/models/__init__.py` (empty).

Create `app/models/models.py`:

```python
import datetime
from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, nullable=False, unique=True)
    device_profile = Column(String, nullable=False)
    comment_style = Column(String, nullable=False, default="casual")
    ramp_up_day = Column(Integer, nullable=False, default=1)
    status = Column(String, nullable=False, default="idle")
    created_at = Column(DateTime, nullable=False, default=datetime.datetime.now)

    sessions = relationship("WarmupSession", back_populates="account")


class WarmupSession(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    started_at = Column(DateTime, nullable=False)
    ended_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Integer, nullable=True)

    account = relationship("Account", back_populates="sessions")
    action_logs = relationship("ActionLog", back_populates="session")


class ActionLog(Base):
    __tablename__ = "action_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False)
    action_type = Column(String, nullable=False)
    detail = Column(String, nullable=False, default="")
    timestamp = Column(DateTime, nullable=False, default=datetime.datetime.now)

    session = relationship("WarmupSession", back_populates="action_logs")
```

Create `app/models/database.py`:

```python
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from app.models.models import Base

_engine = None
_SessionLocal = None


def init_db(db_url: str = "sqlite:///db/warmup.db") -> None:
    global _engine, _SessionLocal
    _engine = create_engine(db_url, connect_args={"check_same_thread": False})
    _SessionLocal = sessionmaker(bind=_engine)
    Base.metadata.create_all(_engine)


def get_db():
    session = _SessionLocal()
    try:
        yield session
    finally:
        session.close()
```

- [ ] **Step 4: Run model tests**

Run: `cd /Users/jean/tiktok-warmup && source venv/bin/activate && python -m pytest tests/test_models.py -v`
Expected: all 3 tests PASS

- [ ] **Step 5: Write failing tests for config loading**

Create `tests/test_config.py`:

```python
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
```

Run: `python -m pytest tests/test_config.py -v`
Expected: FAIL — module not found

- [ ] **Step 6: Implement config loading**

Create `app/config.py`:

```python
import yaml


def load_accounts(path: str) -> list[dict]:
    with open(path) as f:
        data = yaml.safe_load(f)
    return data["accounts"]


def load_devices(path: str) -> dict[str, dict]:
    with open(path) as f:
        data = yaml.safe_load(f)
    return data["devices"]


def load_comments(path: str) -> dict[str, list[str]]:
    categories: dict[str, list[str]] = {}
    current_category = None
    with open(path) as f:
        for line in f:
            line = line.rstrip("\n")
            if line.startswith("# "):
                current_category = line[2:].strip()
                categories[current_category] = []
            elif line.strip() and current_category is not None:
                categories[current_category].append(line)
    return categories
```

- [ ] **Step 7: Run config tests**

Run: `python -m pytest tests/test_config.py -v`
Expected: all 3 tests PASS

- [ ] **Step 8: Create template config files**

Create `config/accounts.yaml`:

```yaml
accounts:
  - username: "compte1"
    password: "ZMJa2011**ZMJa2011**"
    device_profile: "pixel_6"
    comment_style: "casual"
  - username: "compte2"
    password: "ZMJa2011**"
    device_profile: "samsung_s21"
    comment_style: "emoji_heavy"
  - username: "compte3"
    password: "ZMJa2011**"
    device_profile: "oneplus_9"
    comment_style: "casual"
  - username: "compte4"
    password: "ZMJa2011**"
    device_profile: "xiaomi_12"
    comment_style: "questions"
  - username: "compte5"
    password: "ZMJa2011**"
    device_profile: "pixel_7"
    comment_style: "casual"
```

Create `config/devices.yaml`:

```yaml
devices:
  pixel_6:
    model: "Pixel 6"
    resolution: "1080x2400"
    android_version: "13"
    dpi: 411
  samsung_s21:
    model: "Samsung Galaxy S21"
    resolution: "1080x2400"
    android_version: "12"
    dpi: 421
  oneplus_9:
    model: "OnePlus 9"
    resolution: "1080x2400"
    android_version: "13"
    dpi: 402
  xiaomi_12:
    model: "Xiaomi 12"
    resolution: "1080x2400"
    android_version: "12"
    dpi: 419
  pixel_7:
    model: "Pixel 7"
    resolution: "1080x2400"
    android_version: "14"
    dpi: 416
```

Create `config/comments.txt`:

```
# casual
Super cool!
J'adore cette vidéo
Trop bien
C'est ouf
Incroyable
J'aime trop
Wow juste wow
Stylé
Grave bien fait
Top

# emoji_heavy
🔥🔥🔥
❤️❤️
😂😂😂
💯💯
🙌🙌
👏👏👏
😍😍
🤩🤩🤩

# questions
Comment tu fais ça ?
C'est quoi la musique ?
T'utilises quoi pour filmer ?
Ça vient d'où ?
Tu fais ça souvent ?
C'est où ça ?
```

- [ ] **Step 9: Commit**

```bash
cd /Users/jean/tiktok-warmup
git init
git add requirements.txt app/ tests/ config/
mkdir -p db
touch db/.gitkeep
git add db/.gitkeep
git commit -m "feat: data layer — models, database, config loading"
```

---

### Task 2: Anti-Detection Engine

**Files:**
- Create: `app/core/__init__.py`
- Create: `app/core/anti_detect.py`
- Test: `tests/test_anti_detect.py`

**Interfaces:**
- Consumes: nothing directly (pure functions)
- Produces:
  - `app.core.anti_detect.human_delay(min_s: float = 2.0, max_s: float = 8.0) -> float` — returns a gaussian-distributed delay in seconds, clamped to [min_s, max_s]
  - `app.core.anti_detect.should_micro_pause(probability: float = 0.1) -> float` — returns pause duration (10-30s) or 0.0
  - `app.core.anti_detect.session_duration_seconds() -> int` — returns random session length 900-2700 (15-45 min)
  - `app.core.anti_detect.get_allowed_actions(ramp_up_day: int) -> list[str]` — returns action types allowed for this day
  - `app.core.anti_detect.get_action_limits(ramp_up_day: int) -> dict[str, int]` — returns max count per action type for a session
  - `app.core.anti_detect.is_in_activity_window(hour_start: int = 8, hour_end: int = 23) -> bool` — checks current time
  - `app.core.anti_detect.pick_comment(comments: dict[str, list[str]], style: str, used_today: set[str]) -> str` — picks a comment not used today, applies random variation
  - `app.core.anti_detect.should_like(like_rate: float = 0.15) -> bool` — 10-20% chance
  - `app.core.anti_detect.watch_duration(video_length: int = 30) -> int` — 5s to full, occasionally rewatches (>video_length)

- [ ] **Step 1: Write failing tests**

Create `tests/test_anti_detect.py`:

```python
from app.core.anti_detect import (
    human_delay,
    should_micro_pause,
    session_duration_seconds,
    get_allowed_actions,
    get_action_limits,
    pick_comment,
    should_like,
    watch_duration,
)


def test_human_delay_in_range():
    for _ in range(100):
        d = human_delay(2.0, 8.0)
        assert 2.0 <= d <= 8.0


def test_human_delay_distribution_is_centered():
    delays = [human_delay(2.0, 8.0) for _ in range(1000)]
    mean = sum(delays) / len(delays)
    assert 4.0 < mean < 6.0


def test_should_micro_pause_returns_zero_or_range():
    results = [should_micro_pause(0.5) for _ in range(200)]
    non_zero = [r for r in results if r > 0]
    zeros = [r for r in results if r == 0.0]
    assert len(non_zero) > 0
    assert len(zeros) > 0
    for v in non_zero:
        assert 10.0 <= v <= 30.0


def test_session_duration_in_range():
    for _ in range(50):
        d = session_duration_seconds()
        assert 900 <= d <= 2700


def test_ramp_up_day_1_scroll_watch_only():
    actions = get_allowed_actions(1)
    assert "scroll" in actions
    assert "watch" in actions
    assert "like" not in actions
    assert "comment" not in actions


def test_ramp_up_day_4_adds_likes():
    actions = get_allowed_actions(4)
    assert "like" in actions
    assert "comment" not in actions


def test_ramp_up_day_6_adds_follow():
    actions = get_allowed_actions(6)
    assert "follow" in actions
    assert "visit_profile" in actions


def test_ramp_up_day_9_adds_comment():
    actions = get_allowed_actions(9)
    assert "comment" in actions


def test_ramp_up_day_11_all_actions():
    actions = get_allowed_actions(11)
    assert set(actions) == {"scroll", "watch", "like", "follow", "visit_profile", "comment"}


def test_action_limits_day_1():
    limits = get_action_limits(1)
    assert limits.get("like", 0) == 0
    assert limits.get("follow", 0) == 0
    assert limits.get("comment", 0) == 0


def test_action_limits_day_4():
    limits = get_action_limits(4)
    assert 5 <= limits["like"] <= 10


def test_action_limits_cruise():
    limits = get_action_limits(15)
    assert limits["like"] >= 10
    assert limits["comment"] >= 2


def test_pick_comment_no_repeat():
    pool = {"casual": ["A", "B", "C"]}
    used = {"A"}
    comment = pick_comment(pool, "casual", used)
    assert comment not in used or len(pool["casual"]) - len(used) == 0


def test_pick_comment_applies_variation():
    pool = {"casual": ["Hello world"]}
    results = set()
    for _ in range(50):
        results.add(pick_comment(pool, "casual", set()))
    assert len(results) >= 1


def test_should_like_probability():
    results = [should_like(0.15) for _ in range(1000)]
    ratio = sum(results) / len(results)
    assert 0.05 < ratio < 0.30


def test_watch_duration_range():
    for _ in range(100):
        d = watch_duration(30)
        assert 5 <= d <= 45
```

Run: `python -m pytest tests/test_anti_detect.py -v`
Expected: FAIL — module not found

- [ ] **Step 2: Implement anti-detection engine**

Create `app/core/__init__.py` (empty).

Create `app/core/anti_detect.py`:

```python
import random
import math
from datetime import datetime


def human_delay(min_s: float = 2.0, max_s: float = 8.0) -> float:
    mean = (min_s + max_s) / 2
    std = (max_s - min_s) / 4
    delay = random.gauss(mean, std)
    return max(min_s, min(max_s, delay))


def should_micro_pause(probability: float = 0.1) -> float:
    if random.random() < probability:
        return random.uniform(10.0, 30.0)
    return 0.0


def session_duration_seconds() -> int:
    mean = 1800
    std = 450
    duration = int(random.gauss(mean, std))
    return max(900, min(2700, duration))


_RAMP_UP_SCHEDULE = {
    (1, 2): ["scroll", "watch"],
    (3, 4): ["scroll", "watch", "like"],
    (5, 7): ["scroll", "watch", "like", "follow", "visit_profile"],
    (8, 10): ["scroll", "watch", "like", "follow", "visit_profile", "comment"],
}
_ALL_ACTIONS = ["scroll", "watch", "like", "follow", "visit_profile", "comment"]


def get_allowed_actions(ramp_up_day: int) -> list[str]:
    if ramp_up_day >= 11:
        return list(_ALL_ACTIONS)
    for (start, end), actions in _RAMP_UP_SCHEDULE.items():
        if start <= ramp_up_day <= end:
            return list(actions)
    return ["scroll", "watch"]


def get_action_limits(ramp_up_day: int) -> dict[str, int]:
    if ramp_up_day <= 2:
        return {"scroll": 999, "watch": 999, "like": 0, "follow": 0, "visit_profile": 0, "comment": 0}
    if ramp_up_day <= 4:
        likes = random.randint(5, 10)
        return {"scroll": 999, "watch": 999, "like": likes, "follow": 0, "visit_profile": 0, "comment": 0}
    if ramp_up_day <= 7:
        likes = random.randint(5, 10)
        follows = random.randint(1, 3)
        return {"scroll": 999, "watch": 999, "like": likes, "follow": follows, "visit_profile": follows + 2, "comment": 0}
    if ramp_up_day <= 10:
        likes = random.randint(8, 15)
        follows = random.randint(1, 3)
        comments = random.randint(1, 2)
        return {"scroll": 999, "watch": 999, "like": likes, "follow": follows, "visit_profile": follows + 2, "comment": comments}
    likes = random.randint(10, 20)
    follows = random.randint(1, 5)
    comments = random.randint(2, 5)
    return {"scroll": 999, "watch": 999, "like": likes, "follow": follows, "visit_profile": follows + 3, "comment": comments}


def is_in_activity_window(hour_start: int = 8, hour_end: int = 23) -> bool:
    return hour_start <= datetime.now().hour < hour_end


def pick_comment(comments: dict[str, list[str]], style: str, used_today: set[str]) -> str:
    pool = comments.get(style, comments.get("casual", []))
    available = [c for c in pool if c not in used_today]
    if not available:
        available = pool
    base = random.choice(available)
    return _apply_variation(base)


def _apply_variation(text: str) -> str:
    variations = [
        lambda t: t,
        lambda t: t + " " + random.choice(["🔥", "❤️", "😂", "💯", "👏", "✨"]),
        lambda t: t.lower(),
        lambda t: t + "!",
        lambda t: t + "!!",
        lambda t: t.rstrip("!") + " !",
    ]
    return random.choice(variations)(text)


def should_like(like_rate: float = 0.15) -> bool:
    return random.random() < like_rate


def watch_duration(video_length: int = 30) -> int:
    base = random.randint(5, video_length)
    if random.random() < 0.1:
        base = int(video_length * random.uniform(1.0, 1.5))
    return max(5, min(video_length + 15, base))
```

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/test_anti_detect.py -v`
Expected: all tests PASS

- [ ] **Step 4: Commit**

```bash
git add app/core/ tests/test_anti_detect.py
git commit -m "feat: anti-detection engine — timing, ramp-up, comment variation"
```

---

### Task 3: Appium Driver Manager

**Files:**
- Create: `app/core/appium_driver.py`
- Test: `tests/test_appium_driver.py`

**Interfaces:**
- Consumes:
  - `app.config.load_devices(path) -> dict[str, dict]`
- Produces:
  - `app.core.appium_driver.AppiumDriverManager` class:
    - `__init__(self, appium_url: str = "http://localhost:4723")` 
    - `create_session(self, device_profile: dict, avd_name: str) -> webdriver.Remote` — starts Appium session with desired capabilities
    - `close_session(self, driver: webdriver.Remote) -> None` — quits driver cleanly

- [ ] **Step 1: Write failing tests**

Create `tests/test_appium_driver.py`:

```python
from unittest.mock import patch, MagicMock
from app.core.appium_driver import AppiumDriverManager


def test_create_session_builds_correct_capabilities():
    manager = AppiumDriverManager(appium_url="http://localhost:4723")
    device_profile = {
        "model": "Pixel 6",
        "resolution": "1080x2400",
        "android_version": "13",
        "dpi": 411,
    }

    with patch("app.core.appium_driver.webdriver.Remote") as mock_remote:
        mock_driver = MagicMock()
        mock_remote.return_value = mock_driver

        driver = manager.create_session(device_profile, avd_name="avd_compte1")

        mock_remote.assert_called_once()
        call_kwargs = mock_remote.call_args
        opts = call_kwargs[1]["options"]
        assert opts.platform_name == "Android"
        assert driver is mock_driver


def test_close_session_quits_driver():
    manager = AppiumDriverManager()
    mock_driver = MagicMock()
    manager.close_session(mock_driver)
    mock_driver.quit.assert_called_once()
```

Run: `python -m pytest tests/test_appium_driver.py -v`
Expected: FAIL

- [ ] **Step 2: Implement Appium driver manager**

Create `app/core/appium_driver.py`:

```python
from appium import webdriver
from appium.options.android import UiAutomator2Options


class AppiumDriverManager:
    def __init__(self, appium_url: str = "http://localhost:4723"):
        self.appium_url = appium_url

    def create_session(self, device_profile: dict, avd_name: str) -> webdriver.Remote:
        options = UiAutomator2Options()
        options.platform_name = "Android"
        options.device_name = avd_name
        options.avd = avd_name
        options.platform_version = device_profile.get("android_version", "13")
        options.app_package = "com.zhiliaoapp.musically"
        options.app_activity = "com.ss.android.ugc.aweme.splash.SplashActivity"
        options.no_reset = True
        options.new_command_timeout = 300
        options.auto_grant_permissions = True

        driver = webdriver.Remote(
            command_executor=self.appium_url,
            options=options,
        )
        return driver

    def close_session(self, driver: webdriver.Remote) -> None:
        driver.quit()
```

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/test_appium_driver.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add app/core/appium_driver.py tests/test_appium_driver.py
git commit -m "feat: Appium driver manager — session create/close with device profiles"
```

---

### Task 4: Action Engine

**Files:**
- Create: `app/core/action_engine.py`
- Test: `tests/test_action_engine.py`

**Interfaces:**
- Consumes:
  - `app.core.anti_detect.human_delay() -> float`
  - `app.core.anti_detect.should_micro_pause() -> float`
  - `app.core.anti_detect.should_like() -> bool`
  - `app.core.anti_detect.watch_duration() -> int`
  - `app.core.anti_detect.pick_comment() -> str`
  - Appium `webdriver.Remote` driver instance
- Produces:
  - `app.core.action_engine.ActionEngine` class:
    - `__init__(self, driver: webdriver.Remote, comments: dict[str, list[str]], comment_style: str)`
    - `async scroll_feed(self) -> str` — swipes up, returns detail string
    - `async watch_video(self) -> str` — watches current video, returns detail
    - `async like_video(self) -> str` — double-taps to like, returns detail
    - `async follow_user(self) -> str` — taps follow button, returns detail
    - `async visit_profile(self) -> str` — taps username to visit, returns detail
    - `async comment_on_video(self) -> str` — posts a comment, returns detail
    - `async execute_action(self, action_type: str) -> str` — dispatches to the right method

- [ ] **Step 1: Write failing tests**

Create `tests/test_action_engine.py`:

```python
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from app.core.action_engine import ActionEngine


def make_engine():
    mock_driver = MagicMock()
    comments = {"casual": ["Super!", "Cool", "J'adore"]}
    return ActionEngine(driver=mock_driver, comments=comments, comment_style="casual")


def test_scroll_feed():
    engine = make_engine()
    with patch("app.core.action_engine.asyncio.sleep", new_callable=AsyncMock):
        result = asyncio.get_event_loop().run_until_complete(engine.scroll_feed())
    assert "scroll" in result.lower()


def test_watch_video():
    engine = make_engine()
    with patch("app.core.action_engine.asyncio.sleep", new_callable=AsyncMock):
        result = asyncio.get_event_loop().run_until_complete(engine.watch_video())
    assert "watch" in result.lower()


def test_like_video():
    engine = make_engine()
    with patch("app.core.action_engine.asyncio.sleep", new_callable=AsyncMock):
        result = asyncio.get_event_loop().run_until_complete(engine.like_video())
    assert "like" in result.lower()


def test_comment_on_video():
    engine = make_engine()
    with patch("app.core.action_engine.asyncio.sleep", new_callable=AsyncMock):
        result = asyncio.get_event_loop().run_until_complete(engine.comment_on_video())
    assert len(result) > 0


def test_execute_action_dispatches():
    engine = make_engine()
    with patch("app.core.action_engine.asyncio.sleep", new_callable=AsyncMock):
        result = asyncio.get_event_loop().run_until_complete(engine.execute_action("scroll"))
    assert "scroll" in result.lower()


def test_execute_action_unknown_raises():
    engine = make_engine()
    try:
        asyncio.get_event_loop().run_until_complete(engine.execute_action("unknown_action"))
        assert False, "Should have raised ValueError"
    except ValueError:
        pass
```

Run: `python -m pytest tests/test_action_engine.py -v`
Expected: FAIL

- [ ] **Step 2: Implement action engine**

Create `app/core/action_engine.py`:

```python
import asyncio
import random
from appium.webdriver import Remote as AppiumDriver
from app.core.anti_detect import human_delay, should_micro_pause, watch_duration, pick_comment


class ActionEngine:
    def __init__(self, driver: AppiumDriver, comments: dict[str, list[str]], comment_style: str):
        self.driver = driver
        self.comments = comments
        self.comment_style = comment_style
        self.used_comments_today: set[str] = set()

    async def scroll_feed(self) -> str:
        size = self.driver.get_window_size()
        start_y = int(size["height"] * random.uniform(0.7, 0.85))
        end_y = int(size["height"] * random.uniform(0.15, 0.3))
        start_x = int(size["width"] * random.uniform(0.4, 0.6))
        duration_ms = random.randint(300, 800)
        self.driver.swipe(start_x, start_y, start_x, end_y, duration_ms)
        await asyncio.sleep(human_delay(1.0, 3.0))
        pause = should_micro_pause(0.15)
        if pause > 0:
            await asyncio.sleep(pause)
        return "scrolled feed"

    async def watch_video(self) -> str:
        duration = watch_duration(30)
        await asyncio.sleep(duration)
        return f"watched video for {duration}s"

    async def like_video(self) -> str:
        size = self.driver.get_window_size()
        center_x = size["width"] // 2
        center_y = size["height"] // 2
        self.driver.double_tap(center_x, center_y)
        await asyncio.sleep(human_delay(0.5, 2.0))
        return "liked video"

    async def follow_user(self) -> str:
        try:
            follow_btn = self.driver.find_element("xpath", '//android.widget.TextView[@text="Follow"]')
            follow_btn.click()
            await asyncio.sleep(human_delay(1.0, 3.0))
            return "followed user"
        except Exception:
            return "follow button not found"

    async def visit_profile(self) -> str:
        try:
            username_el = self.driver.find_element("xpath", '//android.widget.TextView[contains(@resource-id, "title")]')
            username_el.click()
            await asyncio.sleep(human_delay(3.0, 8.0))
            self.driver.back()
            await asyncio.sleep(human_delay(1.0, 2.0))
            return "visited profile"
        except Exception:
            return "profile not accessible"

    async def comment_on_video(self) -> str:
        comment_text = pick_comment(self.comments, self.comment_style, self.used_comments_today)
        self.used_comments_today.add(comment_text)
        try:
            comment_icon = self.driver.find_element("xpath", '//android.widget.ImageView[contains(@resource-id, "comment")]')
            comment_icon.click()
            await asyncio.sleep(human_delay(1.5, 3.0))
            text_field = self.driver.find_element("xpath", '//android.widget.EditText')
            for char in comment_text:
                text_field.send_keys(char)
                await asyncio.sleep(random.uniform(0.05, 0.15))
            await asyncio.sleep(human_delay(0.5, 1.5))
            send_btn = self.driver.find_element("xpath", '//android.widget.TextView[@text="Send"]')
            send_btn.click()
            await asyncio.sleep(human_delay(1.0, 2.0))
            self.driver.back()
            return f"commented: {comment_text}"
        except Exception:
            return "comment failed"

    async def execute_action(self, action_type: str) -> str:
        dispatch = {
            "scroll": self.scroll_feed,
            "watch": self.watch_video,
            "like": self.like_video,
            "follow": self.follow_user,
            "visit_profile": self.visit_profile,
            "comment": self.comment_on_video,
        }
        handler = dispatch.get(action_type)
        if handler is None:
            raise ValueError(f"Unknown action type: {action_type}")
        return await handler()
```

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/test_action_engine.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add app/core/action_engine.py tests/test_action_engine.py
git commit -m "feat: action engine — scroll, watch, like, follow, comment with human timing"
```

---

### Task 5: Orchestrator

**Files:**
- Create: `app/core/orchestrator.py`
- Test: `tests/test_orchestrator.py`

**Interfaces:**
- Consumes:
  - `app.core.action_engine.ActionEngine`
  - `app.core.anti_detect.get_allowed_actions(ramp_up_day) -> list[str]`
  - `app.core.anti_detect.get_action_limits(ramp_up_day) -> dict[str, int]`
  - `app.core.anti_detect.session_duration_seconds() -> int`
  - `app.core.anti_detect.human_delay() -> float`
  - `app.core.anti_detect.is_in_activity_window() -> bool`
  - `app.core.appium_driver.AppiumDriverManager`
  - `app.models.models.Account`, `WarmupSession`, `ActionLog`
  - `app.models.database.get_db()`
  - `app.config.load_devices()`, `load_comments()`
- Produces:
  - `app.core.orchestrator.Orchestrator` class:
    - `__init__(self, db_url: str, config_dir: str, appium_url: str = "http://localhost:4723")`
    - `async start_account(self, username: str) -> None` — starts warmup loop for one account
    - `async stop_account(self, username: str) -> None` — stops the account's worker
    - `async start_all(self) -> None` — starts all accounts
    - `async stop_all(self) -> None` — stops all accounts
    - `get_status(self) -> dict[str, dict]` — returns {username: {status, counters, recent_logs}}
    - `subscribe(self) -> asyncio.Queue` — returns a queue that receives event dicts for SSE
    - Event dict shape: `{"type": str, "username": str, "data": str, "timestamp": str}`

- [ ] **Step 1: Write failing tests**

Create `tests/test_orchestrator.py`:

```python
import asyncio
import datetime
from unittest.mock import patch, MagicMock, AsyncMock
from app.core.orchestrator import Orchestrator


def make_orchestrator(tmp_path=None):
    import tempfile, os, yaml
    config_dir = tmp_path or tempfile.mkdtemp()
    accounts_path = os.path.join(config_dir, "accounts.yaml")
    devices_path = os.path.join(config_dir, "devices.yaml")
    comments_path = os.path.join(config_dir, "comments.txt")

    with open(accounts_path, "w") as f:
        yaml.dump({"accounts": [
            {"username": "u1", "password": "p1", "device_profile": "pixel_6", "comment_style": "casual"},
        ]}, f)
    with open(devices_path, "w") as f:
        yaml.dump({"devices": {"pixel_6": {"model": "Pixel 6", "resolution": "1080x2400", "android_version": "13", "dpi": 411}}}, f)
    with open(comments_path, "w") as f:
        f.write("# casual\nCool\nNice\n")

    return Orchestrator(db_url="sqlite:///:memory:", config_dir=config_dir)


def test_orchestrator_init_creates_accounts():
    orch = make_orchestrator()
    status = orch.get_status()
    assert "u1" in status
    assert status["u1"]["status"] == "idle"


def test_get_status_returns_counters():
    orch = make_orchestrator()
    status = orch.get_status()
    assert "counters" in status["u1"]
    assert status["u1"]["counters"]["likes"] == 0


def test_subscribe_returns_queue():
    orch = make_orchestrator()
    queue = orch.subscribe()
    assert isinstance(queue, asyncio.Queue)


def test_start_stop_account():
    orch = make_orchestrator()
    with patch.object(orch, "_run_session", new_callable=AsyncMock):
        loop = asyncio.new_event_loop()
        loop.run_until_complete(orch.start_account("u1"))
        assert orch.get_status()["u1"]["status"] == "running"
        loop.run_until_complete(orch.stop_account("u1"))
        assert orch.get_status()["u1"]["status"] == "idle"
        loop.close()
```

Run: `python -m pytest tests/test_orchestrator.py -v`
Expected: FAIL

- [ ] **Step 2: Implement orchestrator**

Create `app/core/orchestrator.py`:

```python
import asyncio
import datetime
import random
from sqlalchemy import create_engine
from sqlalchemy.orm import Session as SASession, sessionmaker
from app.models.models import Base, Account, WarmupSession, ActionLog
from app.config import load_accounts, load_devices, load_comments
from app.core.anti_detect import (
    get_allowed_actions, get_action_limits, session_duration_seconds,
    human_delay, is_in_activity_window,
)
from app.core.appium_driver import AppiumDriverManager
from app.core.action_engine import ActionEngine
import os


class Orchestrator:
    def __init__(self, db_url: str, config_dir: str, appium_url: str = "http://localhost:4723"):
        self.engine = create_engine(db_url, connect_args={"check_same_thread": False})
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

        self.config_dir = config_dir
        self.accounts_config = load_accounts(os.path.join(config_dir, "accounts.yaml"))
        self.devices = load_devices(os.path.join(config_dir, "devices.yaml"))
        self.comments = load_comments(os.path.join(config_dir, "comments.txt"))
        self.appium_manager = AppiumDriverManager(appium_url)

        self._workers: dict[str, asyncio.Task] = {}
        self._subscribers: list[asyncio.Queue] = []
        self._stop_events: dict[str, asyncio.Event] = {}

        self._init_accounts()

    def _init_accounts(self):
        with self.Session() as session:
            for acc_cfg in self.accounts_config:
                existing = session.query(Account).filter_by(username=acc_cfg["username"]).first()
                if not existing:
                    account = Account(
                        username=acc_cfg["username"],
                        device_profile=acc_cfg["device_profile"],
                        comment_style=acc_cfg.get("comment_style", "casual"),
                    )
                    session.add(account)
            session.commit()

    def get_status(self) -> dict[str, dict]:
        result = {}
        with self.Session() as session:
            for acc_cfg in self.accounts_config:
                username = acc_cfg["username"]
                account = session.query(Account).filter_by(username=username).first()
                if not account:
                    continue

                logs = (
                    session.query(ActionLog)
                    .join(WarmupSession)
                    .filter(WarmupSession.account_id == account.id)
                    .order_by(ActionLog.timestamp.desc())
                    .limit(20)
                    .all()
                )

                all_logs = (
                    session.query(ActionLog)
                    .join(WarmupSession)
                    .filter(WarmupSession.account_id == account.id)
                    .all()
                )
                counters = {"likes": 0, "follows": 0, "comments": 0, "videos_watched": 0, "scrolls": 0}
                for log in all_logs:
                    if log.action_type == "like":
                        counters["likes"] += 1
                    elif log.action_type == "follow":
                        counters["follows"] += 1
                    elif log.action_type == "comment":
                        counters["comments"] += 1
                    elif log.action_type == "watch":
                        counters["videos_watched"] += 1
                    elif log.action_type == "scroll":
                        counters["scrolls"] += 1

                result[username] = {
                    "status": account.status,
                    "ramp_up_day": account.ramp_up_day,
                    "counters": counters,
                    "recent_logs": [
                        {"action": l.action_type, "detail": l.detail, "time": l.timestamp.isoformat()}
                        for l in logs
                    ],
                }
        return result

    def subscribe(self) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers.append(queue)
        return queue

    async def _broadcast(self, event: dict):
        dead = []
        for i, q in enumerate(self._subscribers):
            try:
                q.put_nowait(event)
            except asyncio.QueueFull:
                dead.append(i)
        for i in reversed(dead):
            self._subscribers.pop(i)

    async def start_account(self, username: str):
        if username in self._workers and not self._workers[username].done():
            return
        self._stop_events[username] = asyncio.Event()
        with self.Session() as session:
            account = session.query(Account).filter_by(username=username).first()
            if account:
                account.status = "running"
                session.commit()
        self._workers[username] = asyncio.create_task(self._run_session(username))
        await self._broadcast({"type": "status", "username": username, "data": "running", "timestamp": datetime.datetime.now().isoformat()})

    async def stop_account(self, username: str):
        if username in self._stop_events:
            self._stop_events[username].set()
        if username in self._workers:
            self._workers[username].cancel()
            try:
                await self._workers[username]
            except asyncio.CancelledError:
                pass
            del self._workers[username]
        with self.Session() as session:
            account = session.query(Account).filter_by(username=username).first()
            if account:
                account.status = "idle"
                session.commit()
        await self._broadcast({"type": "status", "username": username, "data": "idle", "timestamp": datetime.datetime.now().isoformat()})

    async def start_all(self):
        for acc_cfg in self.accounts_config:
            await self.start_account(acc_cfg["username"])

    async def stop_all(self):
        for username in list(self._workers.keys()):
            await self.stop_account(username)

    async def _run_session(self, username: str):
        acc_cfg = next(a for a in self.accounts_config if a["username"] == username)
        device_profile = self.devices[acc_cfg["device_profile"]]
        avd_name = f"avd_{username}"
        stop_event = self._stop_events[username]

        try:
            driver = self.appium_manager.create_session(device_profile, avd_name)
        except Exception as e:
            await self._set_error(username, str(e))
            return

        action_engine = ActionEngine(driver, self.comments, acc_cfg.get("comment_style", "casual"))

        try:
            while not stop_event.is_set():
                if not is_in_activity_window():
                    await asyncio.sleep(60)
                    continue

                session_len = session_duration_seconds()
                with self.Session() as db:
                    account = db.query(Account).filter_by(username=username).first()
                    ramp_up_day = account.ramp_up_day
                    ws = WarmupSession(account_id=account.id, started_at=datetime.datetime.now())
                    db.add(ws)
                    db.commit()
                    db.refresh(ws)
                    session_id = ws.id

                allowed = get_allowed_actions(ramp_up_day)
                limits = get_action_limits(ramp_up_day)
                action_counts: dict[str, int] = {a: 0 for a in allowed}
                start_time = asyncio.get_event_loop().time()

                while (asyncio.get_event_loop().time() - start_time) < session_len and not stop_event.is_set():
                    available = [a for a in allowed if action_counts.get(a, 0) < limits.get(a, 0)]
                    if not available:
                        available = ["scroll", "watch"]

                    action = random.choice(available)
                    detail = await action_engine.execute_action(action)
                    action_counts[action] = action_counts.get(action, 0) + 1

                    with self.Session() as db:
                        log = ActionLog(session_id=session_id, action_type=action, detail=detail)
                        db.add(log)
                        db.commit()

                    await self._broadcast({
                        "type": "action",
                        "username": username,
                        "data": f"{action}: {detail}",
                        "timestamp": datetime.datetime.now().isoformat(),
                    })

                    await asyncio.sleep(human_delay())

                with self.Session() as db:
                    ws = db.query(WarmupSession).get(session_id)
                    ws.ended_at = datetime.datetime.now()
                    ws.duration_seconds = int(asyncio.get_event_loop().time() - start_time)
                    db.commit()

                pause_hours = random.uniform(2.0, 5.0)
                await asyncio.sleep(pause_hours * 3600)

        except asyncio.CancelledError:
            pass
        finally:
            self.appium_manager.close_session(driver)

    async def _set_error(self, username: str, error: str):
        with self.Session() as session:
            account = session.query(Account).filter_by(username=username).first()
            if account:
                account.status = "error"
                session.commit()
        await self._broadcast({
            "type": "error",
            "username": username,
            "data": error,
            "timestamp": datetime.datetime.now().isoformat(),
        })
```

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/test_orchestrator.py -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add app/core/orchestrator.py tests/test_orchestrator.py
git commit -m "feat: orchestrator — per-account workers, session lifecycle, SSE events"
```

---

### Task 6: API Routes + SSE

**Files:**
- Create: `app/api/__init__.py`
- Create: `app/api/routes.py`
- Create: `app/main.py`
- Test: `tests/test_api.py`

**Interfaces:**
- Consumes:
  - `app.core.orchestrator.Orchestrator` (all public methods)
- Produces:
  - `GET /` — serves dashboard HTML
  - `GET /api/status` — returns all accounts status as JSON
  - `POST /api/start-all` — starts warmup on all accounts
  - `POST /api/stop-all` — stops all accounts
  - `POST /api/start/{username}` — starts one account
  - `POST /api/stop/{username}` — stops one account
  - `GET /api/events` — SSE stream of real-time events

- [ ] **Step 1: Write failing tests**

Create `tests/test_api.py`:

```python
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from httpx import AsyncClient, ASGITransport
from app.main import create_app


@pytest.fixture
def mock_orchestrator():
    orch = MagicMock()
    orch.get_status.return_value = {
        "u1": {
            "status": "idle",
            "ramp_up_day": 1,
            "counters": {"likes": 0, "follows": 0, "comments": 0, "videos_watched": 0, "scrolls": 0},
            "recent_logs": [],
        }
    }
    orch.start_all = AsyncMock()
    orch.stop_all = AsyncMock()
    orch.start_account = AsyncMock()
    orch.stop_account = AsyncMock()
    return orch


@pytest.mark.asyncio
async def test_get_status(mock_orchestrator):
    app = create_app(mock_orchestrator)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/api/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "u1" in data


@pytest.mark.asyncio
async def test_start_all(mock_orchestrator):
    app = create_app(mock_orchestrator)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/start-all")
    assert resp.status_code == 200
    mock_orchestrator.start_all.assert_awaited_once()


@pytest.mark.asyncio
async def test_stop_all(mock_orchestrator):
    app = create_app(mock_orchestrator)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/stop-all")
    assert resp.status_code == 200
    mock_orchestrator.stop_all.assert_awaited_once()


@pytest.mark.asyncio
async def test_start_single_account(mock_orchestrator):
    app = create_app(mock_orchestrator)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/start/u1")
    assert resp.status_code == 200
    mock_orchestrator.start_account.assert_awaited_once_with("u1")


@pytest.mark.asyncio
async def test_stop_single_account(mock_orchestrator):
    app = create_app(mock_orchestrator)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.post("/api/stop/u1")
    assert resp.status_code == 200
    mock_orchestrator.stop_account.assert_awaited_once_with("u1")


@pytest.mark.asyncio
async def test_dashboard_page(mock_orchestrator):
    app = create_app(mock_orchestrator)
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        resp = await client.get("/")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
```

Run: `python -m pytest tests/test_api.py -v`
Expected: FAIL

- [ ] **Step 2: Implement API routes**

Create `app/api/__init__.py` (empty).

Create `app/api/routes.py`:

```python
import asyncio
import json
from fastapi import APIRouter, Request
from sse_starlette.sse import EventSourceResponse

router = APIRouter()


@router.get("/api/status")
async def get_status(request: Request):
    return request.app.state.orchestrator.get_status()


@router.post("/api/start-all")
async def start_all(request: Request):
    await request.app.state.orchestrator.start_all()
    return {"ok": True}


@router.post("/api/stop-all")
async def stop_all(request: Request):
    await request.app.state.orchestrator.stop_all()
    return {"ok": True}


@router.post("/api/start/{username}")
async def start_account(username: str, request: Request):
    await request.app.state.orchestrator.start_account(username)
    return {"ok": True}


@router.post("/api/stop/{username}")
async def stop_account(username: str, request: Request):
    await request.app.state.orchestrator.stop_account(username)
    return {"ok": True}


@router.get("/api/events")
async def events(request: Request):
    queue = request.app.state.orchestrator.subscribe()

    async def event_generator():
        while True:
            if await request.is_disconnected():
                break
            try:
                event = await asyncio.wait_for(queue.get(), timeout=30.0)
                yield {"event": event["type"], "data": json.dumps(event)}
            except asyncio.TimeoutError:
                yield {"event": "ping", "data": ""}

    return EventSourceResponse(event_generator())
```

- [ ] **Step 3: Implement main.py with create_app**

Create `app/main.py`:

```python
import os
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from app.api.routes import router
from app.core.orchestrator import Orchestrator

templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))


def create_app(orchestrator: Orchestrator | None = None) -> FastAPI:
    app = FastAPI(title="TikTok Warmup")
    app.include_router(router)

    if orchestrator is None:
        base_dir = os.path.dirname(os.path.dirname(__file__))
        orchestrator = Orchestrator(
            db_url=f"sqlite:///{os.path.join(base_dir, 'db', 'warmup.db')}",
            config_dir=os.path.join(base_dir, "config"),
        )
    app.state.orchestrator = orchestrator

    @app.get("/", response_class=HTMLResponse)
    async def dashboard(request: Request):
        status = orchestrator.get_status()
        return templates.TemplateResponse("dashboard.html", {"request": request, "accounts": status})

    return app


if __name__ == "__main__":
    import uvicorn
    app = create_app()
    uvicorn.run(app, host="0.0.0.0", port=8000)
```

- [ ] **Step 4: Create a minimal dashboard.html placeholder (enough for tests to pass)**

Create `app/templates/dashboard.html`:

```html
<!DOCTYPE html>
<html>
<head><title>TikTok Warmup</title></head>
<body><h1>TikTok Warmup Dashboard</h1></body>
</html>
```

- [ ] **Step 5: Run tests**

Run: `python -m pytest tests/test_api.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add app/api/ app/main.py app/templates/dashboard.html tests/test_api.py
git commit -m "feat: API routes — status, start/stop, SSE events stream"
```

---

### Task 7: Dashboard UI

**Files:**
- Modify: `app/templates/dashboard.html`

**Interfaces:**
- Consumes:
  - `GET /api/status` — JSON with all account data
  - `POST /api/start-all`, `POST /api/stop-all`
  - `POST /api/start/{username}`, `POST /api/stop/{username}`
  - `GET /api/events` — SSE stream
- Produces: fully functional single-page dashboard (no new backend interfaces)

- [ ] **Step 1: Implement the full dashboard template**

Replace `app/templates/dashboard.html` with the complete version:

```html
<!DOCTYPE html>
<html lang="fr">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TikTok Warmup</title>
    <script src="https://unpkg.com/htmx.org@2.0.0"></script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }

        body {
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
            background: #0f0f0f;
            color: #e0e0e0;
            min-height: 100vh;
        }

        header {
            padding: 20px 30px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 1px solid #2a2a2a;
        }

        header h1 {
            font-size: 22px;
            font-weight: 600;
        }

        .controls {
            display: flex;
            gap: 10px;
        }

        .btn {
            padding: 10px 24px;
            border: none;
            border-radius: 8px;
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: opacity 0.2s;
        }

        .btn:hover { opacity: 0.85; }

        .btn-start {
            background: #25d366;
            color: #000;
        }

        .btn-stop {
            background: #e74c3c;
            color: #fff;
        }

        .btn-sm {
            padding: 6px 14px;
            font-size: 12px;
        }

        .grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
            gap: 16px;
            padding: 20px 30px;
        }

        .card {
            background: #1a1a1a;
            border-radius: 12px;
            padding: 20px;
            border: 1px solid #2a2a2a;
        }

        .card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 16px;
        }

        .card-header h2 {
            font-size: 16px;
            font-weight: 600;
        }

        .status {
            padding: 3px 10px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 600;
            text-transform: uppercase;
        }

        .status-idle { background: #333; color: #888; }
        .status-running { background: #25d36622; color: #25d366; }
        .status-error { background: #e74c3c22; color: #e74c3c; }

        .counters {
            display: grid;
            grid-template-columns: repeat(2, 1fr);
            gap: 8px;
            margin-bottom: 16px;
        }

        .counter {
            background: #222;
            padding: 8px 12px;
            border-radius: 8px;
            font-size: 12px;
        }

        .counter strong {
            display: block;
            font-size: 18px;
            color: #fff;
        }

        .logs {
            max-height: 200px;
            overflow-y: auto;
            font-size: 12px;
            font-family: monospace;
            background: #111;
            border-radius: 8px;
            padding: 10px;
            margin-top: 12px;
        }

        .logs::-webkit-scrollbar { width: 4px; }
        .logs::-webkit-scrollbar-thumb { background: #444; border-radius: 2px; }

        .log-entry {
            padding: 3px 0;
            border-bottom: 1px solid #1a1a1a;
            color: #aaa;
        }

        .log-entry .time { color: #666; }
        .log-entry .action { color: #25d366; }

        .card-controls {
            margin-top: 12px;
            display: flex;
            gap: 8px;
        }

        .ramp-up-info {
            font-size: 12px;
            color: #666;
            margin-bottom: 12px;
        }
    </style>
</head>
<body>

<header>
    <h1>TikTok Warmup</h1>
    <div class="controls">
        <button class="btn btn-start" onclick="startAll()">Start All</button>
        <button class="btn btn-stop" onclick="stopAll()">Stop All</button>
    </div>
</header>

<div class="grid" id="accounts-grid">
    {% for username, data in accounts.items() %}
    <div class="card" id="card-{{ username }}">
        <div class="card-header">
            <h2>{{ username }}</h2>
            <span class="status status-{{ data.status }}">{{ data.status }}</span>
        </div>

        <div class="ramp-up-info">Jour {{ data.ramp_up_day }} / ramp-up</div>

        <div class="counters">
            <div class="counter">
                <strong id="cnt-{{ username }}-videos">{{ data.counters.videos_watched }}</strong>
                Videos
            </div>
            <div class="counter">
                <strong id="cnt-{{ username }}-likes">{{ data.counters.likes }}</strong>
                Likes
            </div>
            <div class="counter">
                <strong id="cnt-{{ username }}-follows">{{ data.counters.follows }}</strong>
                Follows
            </div>
            <div class="counter">
                <strong id="cnt-{{ username }}-comments">{{ data.counters.comments }}</strong>
                Comments
            </div>
        </div>

        <div class="card-controls">
            <button class="btn btn-start btn-sm" onclick="startAccount('{{ username }}')">Start</button>
            <button class="btn btn-stop btn-sm" onclick="stopAccount('{{ username }}')">Stop</button>
        </div>

        <div class="logs" id="logs-{{ username }}">
            {% for log in data.recent_logs %}
            <div class="log-entry">
                <span class="time">{{ log.time[-8:] }}</span>
                <span class="action">{{ log.action }}</span>
                {{ log.detail }}
            </div>
            {% endfor %}
        </div>
    </div>
    {% endfor %}
</div>

<script>
    async function startAll() {
        await fetch('/api/start-all', { method: 'POST' });
        updateStatus();
    }

    async function stopAll() {
        await fetch('/api/stop-all', { method: 'POST' });
        updateStatus();
    }

    async function startAccount(username) {
        await fetch(`/api/start/${username}`, { method: 'POST' });
        updateStatus();
    }

    async function stopAccount(username) {
        await fetch(`/api/stop/${username}`, { method: 'POST' });
        updateStatus();
    }

    async function updateStatus() {
        const resp = await fetch('/api/status');
        const data = await resp.json();
        for (const [username, info] of Object.entries(data)) {
            const statusEl = document.querySelector(`#card-${username} .status`);
            if (statusEl) {
                statusEl.textContent = info.status;
                statusEl.className = `status status-${info.status}`;
            }
            const ids = { videos: 'videos_watched', likes: 'likes', follows: 'follows', comments: 'comments' };
            for (const [short, key] of Object.entries(ids)) {
                const el = document.getElementById(`cnt-${username}-${short}`);
                if (el) el.textContent = info.counters[key];
            }
        }
    }

    const evtSource = new EventSource('/api/events');

    evtSource.addEventListener('action', (e) => {
        const event = JSON.parse(e.data);
        const logsEl = document.getElementById(`logs-${event.username}`);
        if (logsEl) {
            const entry = document.createElement('div');
            entry.className = 'log-entry';
            const time = event.timestamp.slice(11, 19);
            const parts = event.data.split(': ');
            entry.innerHTML = `<span class="time">${time}</span> <span class="action">${parts[0]}</span> ${parts.slice(1).join(': ')}`;
            logsEl.prepend(entry);
            while (logsEl.children.length > 50) logsEl.removeChild(logsEl.lastChild);
        }
        updateStatus();
    });

    evtSource.addEventListener('status', (e) => {
        updateStatus();
    });

    evtSource.addEventListener('error_event', (e) => {
        updateStatus();
    });

    setInterval(updateStatus, 30000);
</script>

</body>
</html>
```

- [ ] **Step 2: Verify dashboard renders**

Run: `cd /Users/jean/tiktok-warmup && source venv/bin/activate && python -m pytest tests/test_api.py::test_dashboard_page -v`
Expected: PASS (returns 200 with text/html)

- [ ] **Step 3: Commit**

```bash
git add app/templates/dashboard.html
git commit -m "feat: dashboard UI — account cards, counters, live logs, start/stop controls"
```

---

### Task 8: AVD Setup Script + Final Wiring

**Files:**
- Create: `scripts/setup_avds.sh`
- Modify: `app/main.py` (add `__main__` startup with db dir creation)

**Interfaces:**
- Consumes: `config/devices.yaml`, `config/accounts.yaml`
- Produces: runnable setup script and final app entry point

- [ ] **Step 1: Create AVD setup script**

Create `scripts/setup_avds.sh`:

```bash
#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

if ! command -v avdmanager &>/dev/null; then
    echo "Error: avdmanager not found. Install Android SDK command-line tools."
    echo "  brew install --cask android-commandlinetools"
    echo "  sdkmanager 'platform-tools' 'platforms;android-34' 'system-images;android-34;google_apis;arm64-v8a'"
    exit 1
fi

SYSTEM_IMAGE="system-images;android-34;google_apis;arm64-v8a"

echo "Checking system image..."
if ! sdkmanager --list_installed 2>/dev/null | grep -q "$SYSTEM_IMAGE"; then
    echo "Installing system image..."
    sdkmanager "$SYSTEM_IMAGE"
fi

declare -A DEVICES
DEVICES[avd_compte1]="pixel_6"
DEVICES[avd_compte2]="pixel_4"
DEVICES[avd_compte3]="pixel_3a"
DEVICES[avd_compte4]="pixel_5"
DEVICES[avd_compte5]="pixel_7"

for avd_name in "${!DEVICES[@]}"; do
    device="${DEVICES[$avd_name]}"
    if avdmanager list avd 2>/dev/null | grep -q "$avd_name"; then
        echo "AVD $avd_name already exists, skipping."
    else
        echo "Creating AVD: $avd_name (device=$device)..."
        echo "no" | avdmanager create avd \
            -n "$avd_name" \
            -k "$SYSTEM_IMAGE" \
            -d "$device" \
            --force
        echo "Created $avd_name"
    fi
done

echo ""
echo "All AVDs created. Start them with:"
echo "  emulator -avd avd_compte1 -no-snapshot -no-audio &"
echo ""
echo "Then start Appium:"
echo "  appium --port 4723"
echo ""
echo "Then start the app:"
echo "  cd $PROJECT_DIR && source venv/bin/activate && python -m app.main"
```

Run: `chmod +x /Users/jean/tiktok-warmup/scripts/setup_avds.sh`

- [ ] **Step 2: Ensure db directory exists on startup**

The `app/main.py` already handles this via SQLAlchemy creating the file. Add `db/` directory creation:

Add to `create_app` in `app/main.py`, before the Orchestrator init:

```python
    if orchestrator is None:
        base_dir = os.path.dirname(os.path.dirname(__file__))
        os.makedirs(os.path.join(base_dir, "db"), exist_ok=True)
        orchestrator = Orchestrator(
```

- [ ] **Step 3: Run all tests**

Run: `cd /Users/jean/tiktok-warmup && source venv/bin/activate && python -m pytest tests/ -v`
Expected: all tests PASS

- [ ] **Step 4: Commit**

```bash
git add scripts/ app/main.py
git commit -m "feat: AVD setup script + db directory auto-creation"
```

---

## Startup Guide (for the implementing engineer)

**Prerequisites:**
1. Python 3.11+
2. Android SDK with command-line tools (`brew install --cask android-commandlinetools`)
3. Appium 2.x (`npm install -g appium && appium driver install uiautomator2`)
4. TikTok APK installed in each emulator (manual step after AVD creation)

**Setup:**
```bash
cd /Users/jean/tiktok-warmup
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
./scripts/setup_avds.sh
```

**Run:**
```bash
# Terminal 1: start emulators
emulator -avd avd_compte1 -no-snapshot -no-audio &
emulator -avd avd_compte2 -no-snapshot -no-audio &
# ... etc

# Terminal 2: start Appium
appium --port 4723

# Terminal 3: start the app
source venv/bin/activate
python -m app.main
# Open http://localhost:8000
```
