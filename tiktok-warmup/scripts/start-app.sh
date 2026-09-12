#!/usr/bin/env bash
# Terminal 2 — Lance le dashboard warmup (http://localhost:8000)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/lib.sh"
load_env
activate_venv

cd "$ROOT"

echo "=== TikTok Warmup ==="
echo ""

# iPhone
if ! check_iphone; then
    echo "⚠️  iPhone non détecté — branche-le en USB avant de lancer une session"
else
    echo "✅ iPhone connecté"
fi

# WDA
if url=$(detect_wda_url); then
    export WDA_URL="$url"
    echo "✅ WDA : $WDA_URL"
else
    echo "❌ WebDriverAgent inaccessible"
    echo ""
    echo "Dans un AUTRE terminal, lance d'abord :"
    echo "  cd $ROOT && ./scripts/start-wda.sh"
    echo ""
    echo "Attends le message « ServerURLHere->http://...:8100 »"
    echo "Puis relance ce script."
    exit 1
fi

echo ""
echo "🌐 Dashboard : http://localhost:${WARMUP_PORT}"
echo "   1. Choisis ton compte"
echo "   2. Ouvre TikTok sur le feed (Accueil ▶)"
echo "   3. Clique « Lancer le warmup »"
echo ""

# Ouvre le navigateur (Mac)
if [[ "$(uname)" == "Darwin" ]]; then
    sleep 1
    open "http://localhost:${WARMUP_PORT}" 2>/dev/null || true
fi

export WDA_URL
exec python -m app.main
