#!/usr/bin/env python3
"""Point d'entrée CLI — warmup TikTok sur iPhone physique."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# Ajouter la racine du package au path
ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(ROOT))

from src.session.warmup_session import WarmupSession, list_profiles
from src.utils.logger import setup_logger


def main() -> int:
    load_dotenv(ROOT / ".env")

    parser = argparse.ArgumentParser(
        description="TikTok Warmup — simule un comportement humain sur iPhone via Appium"
    )
    parser.add_argument(
        "--profile",
        "-p",
        default=os.getenv("WARMUP_PROFILE", "observer"),
        choices=list_profiles(),
        help="Profil de warmup (progression d'engagement)",
    )
    parser.add_argument(
        "--duration",
        "-d",
        type=int,
        default=int(os.getenv("SESSION_DURATION_MINUTES", "0")),
        help="Durée session en minutes (0 = valeur du profil)",
    )
    parser.add_argument(
        "--list-profiles",
        action="store_true",
        help="Affiche les profils disponibles",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Affiche la config sans lancer Appium",
    )
    args = parser.parse_args()

    log_dir = ROOT / "logs"
    logger = setup_logger(log_dir=log_dir)

    if args.list_profiles:
        for name in list_profiles():
            session = WarmupSession(profile_name=name)
            logger.info("%s: %s", name, session.profile.description)
        return 0

    if args.dry_run:
        session = WarmupSession(
            profile_name=args.profile,
            session_duration_override=args.duration,
        )
        logger.info("Mode dry-run — configuration:")
        logger.info("  Profil: %s", session.profile.name)
        logger.info("  Device: %s", session.ios.get_capabilities_summary())
        logger.info("  Like prob: %.0f%%", session.profile.like_probability * 100)
        logger.info("  Durée: %d min", session.profile.session_duration_minutes)
        return 0

    logger.info("Démarrage warmup — profil '%s'", args.profile)
    logger.info("Assurez-vous qu'Appium tourne: appium --relaxed-security")

    session = WarmupSession(
        profile_name=args.profile,
        session_duration_override=args.duration,
        log_dir=log_dir,
    )
    session.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
