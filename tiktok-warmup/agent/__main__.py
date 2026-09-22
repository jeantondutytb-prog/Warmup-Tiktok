"""Point d'entrée : `python3 -m agent` (géré automatiquement par le Mac)."""

from __future__ import annotations

import argparse
import asyncio
import os
import pathlib

from agent.bridge import run_bridge
from agent.wda import WDASupervisor, preferred_udid


def _load_dotenv() -> None:
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


def main() -> None:
    _load_dotenv()
    parser = argparse.ArgumentParser(description="Agent warmup Mac → Vercel")
    parser.add_argument("command", nargs="?", default="run", choices=["run", "install", "status"])
    args = parser.parse_args()

    if args.command == "install":
        from agent.install_mac import install
        install()
        return

    if args.command == "status":
        wda = WDASupervisor()
        print(wda.refresh())
        print("udid:", preferred_udid())
        return

    asyncio.run(run_bridge())


if __name__ == "__main__":
    main()
