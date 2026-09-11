# TikTok Warmup App — Design Spec

## Purpose

Local app to warm up 1-5 TikTok accounts by simulating realistic human behavior (scroll, watch, like, follow, visit profiles, comment) before posting content. Must be undetectable as a bot.

## Architecture

```
Dashboard (FastAPI + Jinja2 + HTMX, single page)
  5 account cards + central Start/Stop buttons
       │ HTTP / SSE (real-time logs)
       ▼
FastAPI Backend
  ├── Orchestrator (1 async worker per account)
  ├── Action Engine (scroll, like, comment, follow, visit)
  ├── Anti-Detection Layer (human timing, ramp-up, randomization)
  └── Appium Client (1 session per AVD)
       │
       ▼
Android Emulators (1 AVD per account, unique device profile)
```

## Stack

| Component | Technology |
|-----------|-----------|
| Backend | Python 3.11+ / FastAPI |
| Dashboard | Jinja2 + HTMX + SSE |
| DB | SQLite + SQLAlchemy |
| Automation | Appium 2.x (Python client) |
| Emulators | Android SDK (AVDs via avdmanager) |
| Styling | Simple CSS (no framework) |

## Dashboard

Single page with:
- 5 account cards showing: name, status (idle/running/error), live counters (videos watched, likes, follows, comments), scrollable action log
- Central controls: Start All, Stop All
- Per-card controls: Start/Stop individual account

## Warmup Actions

| Action | Behavior |
|--------|----------|
| Scroll feed | Variable speed swipe, random pause on videos (3-30s) |
| Watch | Stay 5s to full duration, occasional rewatch |
| Like | ~10-20% of watched videos, never in bursts |
| Follow | 1-5 accounts per session, from feed or suggestions |
| Visit profile | Click profile, scroll their videos, sometimes like an old one |
| Comment | 2-5 per session, from a pool of varied natural phrases |

Session duration: 15-45 min (randomized). 1-3 sessions per day, spaced by hours.

## Anti-Detection

### Human-like timing
- Inter-action delay: 2-8s (gaussian distribution)
- Random micro-pauses: 10-30s
- Session start time varies ±30 min daily
- Activity window: configurable (default 8h-23h)

### Progressive ramp-up
| Day | Allowed actions |
|-----|----------------|
| 1-2 | Scroll + watch only |
| 3-4 | + likes (5-10/session) |
| 5-7 | + follow (1-3/session) + profile visits |
| 8-10 | + comments (1-2/session) |
| 11+ | Cruise mode, all actions |

Configurable per account (each tracks its own ramp-up day).

### Device fingerprinting
- Each AVD: unique device name, resolution, Android version
- Config file per account mapping to a device profile
- Emulators never share the same configuration

### Natural comments
- Pool of comments in a text file, organized by category (funny, positive, question, emoji)
- No repeat within same day
- Random variation: emoji addition, punctuation, capitalization

## Data Model (SQLite)

### accounts
id, username, device_profile, ramp_up_day, status, created_at

### sessions
id, account_id, started_at, ended_at, duration_seconds

### action_logs
id, session_id, action_type, detail, timestamp

## Project Structure

```
tiktok-warmup/
├── app/
│   ├── main.py
│   ├── api/
│   │   └── routes.py
│   ├── core/
│   │   ├── orchestrator.py
│   │   ├── action_engine.py
│   │   ├── anti_detect.py
│   │   └── appium_driver.py
│   ├── models/
│   │   └── models.py
│   └── templates/
│       └── dashboard.html
├── config/
│   ├── accounts.yaml
│   ├── devices.yaml
│   └── comments.txt
├── db/
├── scripts/
│   └── setup_avds.sh
├── requirements.txt
└── README.md
```

## Configuration (accounts.yaml)

```yaml
accounts:
  - username: "compte1"
    password: "xxx"
    device_profile: "pixel_6"
    comment_style: "casual"
  - username: "compte2"
    password: "xxx"
    device_profile: "samsung_s21"
    comment_style: "emoji_heavy"
```

Passwords stored locally only, never transmitted.

## Out of Scope (for later)
- Proxy support (1 proxy per account)
- Content posting
- Analytics/reporting beyond live counters
- Multi-machine deployment
