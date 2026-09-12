#!/usr/bin/env bash
# Lance TikTok Studio Hub et ouvre le navigateur (Mac / Linux)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

if [[ ! -d venv ]]; then
  echo "Installation des dépendances…"
  python3 -m venv venv
  ./venv/bin/pip install -q -r requirements.txt
fi

if [[ ! -f .env ]]; then
  cp .env.example .env
  echo "Fichier .env créé — ajoutez vos clés TikTok avant de connecter un compte."
fi

# Arrête une instance déjà lancée sur le port 8080
if lsof -ti:8080 >/dev/null 2>&1; then
  echo "Port 8080 déjà utilisé — réutilisation du serveur existant."
else
  echo "Démarrage du serveur sur http://localhost:8080 …"
  nohup ./venv/bin/python3 -m app.main > studio.log 2>&1 &
  sleep 2
fi

URL="http://localhost:8080/"

if [[ "$(uname)" == "Darwin" ]]; then
  open "$URL"
elif command -v xdg-open >/dev/null; then
  xdg-open "$URL" >/dev/null 2>&1 || true
else
  echo "Ouvrez manuellement : $URL"
fi

echo ""
echo "  TikTok Studio Hub → $URL"
echo "  1. Copiez vos clés dans .env (TIKTOK_CLIENT_KEY / TIKTOK_CLIENT_SECRET)"
echo "  2. Cliquez « + Ajouter un compte » pour connecter chaque compte TikTok"
echo ""
