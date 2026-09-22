"""Installation Mac sans terminal : appelé par le .command double-cliqué."""

from __future__ import annotations

import pathlib
import shutil
import subprocess
import sys
import textwrap

PLIST_LABEL = "com.peachtint.warmup"


def repo_root() -> pathlib.Path:
    return pathlib.Path(__file__).resolve().parent.parent


def find_python3() -> pathlib.Path:
    for candidate in (
        shutil.which("python3"),
        "/opt/homebrew/bin/python3",
        "/usr/local/bin/python3",
        "/usr/bin/python3",
    ):
        if candidate and pathlib.Path(candidate).exists():
            return pathlib.Path(candidate)
    raise RuntimeError("python3 introuvable — installe Xcode Command Line Tools")


def ensure_venv(root: pathlib.Path) -> pathlib.Path:
    py = root / "venv" / "bin" / "python3"
    if py.exists():
        return py
    base = find_python3()
    print(f"Création du venv avec {base}…")
    subprocess.run([str(base), "-m", "venv", str(root / "venv")], check=True)
    py = root / "venv" / "bin" / "python3"
    print("Installation des dépendances…")
    subprocess.run([str(py), "-m", "pip", "install", "-q", "-r", str(root / "requirements.txt")], check=True)
    return py


def ensure_env_file(root: pathlib.Path) -> None:
    dest = root / ".env.agent"
    if dest.exists():
        return
    example = root / ".env.agent.example"
    if example.exists():
        dest.write_text(example.read_text())
        print(f"Config créée : {dest}")
    else:
        raise RuntimeError(".env.agent.example manquant")


def write_plist(root: pathlib.Path, python: pathlib.Path) -> pathlib.Path:
    dest = pathlib.Path.home() / "Library" / "LaunchAgents" / f"{PLIST_LABEL}.plist"
    dest.parent.mkdir(parents=True, exist_ok=True)
    (root / "db").mkdir(parents=True, exist_ok=True)
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
    return dest


def launchctl_bootstrap(plist: pathlib.Path) -> None:
    uid = subprocess.check_output(["id", "-u"], text=True).strip()
    domain = f"gui/{uid}"
    subprocess.run(
        ["launchctl", "bootout", domain, str(plist)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    subprocess.run(["launchctl", "bootstrap", domain, str(plist)], check=True)


def install() -> None:
    root = repo_root()
    python = ensure_venv(root)
    ensure_env_file(root)
    plist = write_plist(root, python)
    launchctl_bootstrap(plist)
    print("")
    print("✓ Warmup actif sur ce Mac (démarrage auto à chaque connexion).")
    print("  Branche l’iPhone, ouvre https://tiktok-warmup-ten.vercel.app")
    print("  → Start Warm Up")
    print("")


if __name__ == "__main__":
    try:
        install()
    except subprocess.CalledProcessError as exc:
        print(f"Erreur installation : {exc}", file=sys.stderr)
        sys.exit(1)
