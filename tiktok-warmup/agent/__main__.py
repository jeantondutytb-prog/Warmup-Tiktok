"""Point d'entrée : `python -m agent`.

Le dashboard Vercel envoie les Start/Stop. Ici on garde WDA vivant et on
exécute les sessions sur l'iPhone branché.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import pathlib
import textwrap

from agent.bridge import run_bridge
from agent.wda import WDASupervisor, preferred_udid


PLIST_LABEL = "com.peachtint.warmup"


def _load_dotenv() -> None:
    """Charge `.env.agent` s'il existe, sans écraser l'environnement déjà posé."""
    root = pathlib.Path(__file__).resolve().parent.parent
    path = root / ".env.agent"
    if not path.exists():
        return
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


def install_launchd() -> pathlib.Path:
    """Installe un LaunchAgent pour lancer l'agent à l'ouverture de session."""
    root = pathlib.Path(__file__).resolve().parent.parent
    python = root / "venv" / "bin" / "python"
    if not python.exists():
        python = pathlib.Path("/usr/bin/python3")
    dest = pathlib.Path.home() / "Library" / "LaunchAgents" / f"{PLIST_LABEL}.plist"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_text(textwrap.dedent(f"""\
        <?xml version="1.0" encoding="UTF-8"?>
        <!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
        <plist version="1.0">
        <dict>
            <key>Label</key><string>{PLIST_LABEL}</string>
            <key>WorkingDirectory</key><string>{root}</string>
            <key>ProgramArguments</key>
            <array>
                <string>{python}</string>
                <string>-m</string>
                <string>agent</string>
            </array>
            <key>RunAtLoad</key><true/>
            <key>KeepAlive</key><true/>
            <key>StandardOutPath</key><string>{root / 'db' / 'agent.stdout.log'}</string>
            <key>StandardErrorPath</key><string>{root / 'db' / 'agent.stderr.log'}</string>
        </dict>
        </plist>
    """))
    print(f"LaunchAgent écrit : {dest}")
    print(f"Charger : launchctl load {dest}")
    return dest


def main() -> None:
    _load_dotenv()
    parser = argparse.ArgumentParser(description="Agent warmup Mac → Vercel")
    parser.add_argument("command", nargs="?", default="run", choices=["run", "install", "status"])
    args = parser.parse_args()

    if args.command == "install":
        install_launchd()
        return

    if args.command == "status":
        wda = WDASupervisor()
        print(wda.refresh())
        print("udid:", preferred_udid())
        return

    print("agent warmup — Ctrl+C pour quitter", flush=True)
    print(f"cockpit : {os.environ.get('WARMUP_URL', '(WARMUP_URL manquant)')}", flush=True)
    asyncio.run(run_bridge())


if __name__ == "__main__":
    main()
