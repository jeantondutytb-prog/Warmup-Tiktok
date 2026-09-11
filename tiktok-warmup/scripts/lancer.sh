#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════
#  LANCE TOUT — script principal (Mac)
#
#  Usage :
#    cd tiktok-warmup
#    chmod +x scripts/*.sh
#    ./scripts/lancer.sh
# ═══════════════════════════════════════════════════════════════
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/lib.sh"
load_env

echo ""
echo "  ╔══════════════════════════════════════╗"
echo "  ║     TikTok Warmup — Lancement        ║"
echo "  ╚══════════════════════════════════════╝"
echo ""

# Setup auto si premier lancement
if [[ ! -d "$ROOT/venv" ]]; then
    echo "Premier lancement — installation..."
    "$ROOT/scripts/setup-mac.sh"
    echo ""
fi

activate_venv

# ── Étape 1 : iPhone ──────────────────────────────────────────
echo "📱 Étape 1/3 — iPhone"
if ! check_iphone; then
    echo ""
    echo "   ❌ iPhone non détecté"
    echo "   → Branche-le en USB"
    echo "   → Déverrouille l'écran"
    echo "   → Accepte « Faire confiance » sur le Mac"
    echo ""
    read -r -p "   Appuie sur Entrée quand c'est fait... "
    if ! check_iphone; then
        echo "   Toujours pas détecté. Vérifie le câble USB."
        exit 1
    fi
fi
echo "   ✅ iPhone OK"
echo ""

# ── Étape 2 : WebDriverAgent ──────────────────────────────────
echo "🔧 Étape 2/3 — WebDriverAgent"

if url=$(detect_wda_url); then
    export WDA_URL="$url"
    echo "   ✅ WDA déjà actif : $WDA_URL"
else
    echo ""
    echo "   WDA n'est pas encore lancé."
    echo ""
    if [[ "$(uname)" == "Darwin" ]]; then
        echo "   → J'ouvre un nouveau terminal pour WDA..."
        osascript <<APPLESCRIPT
tell application "Terminal"
    activate
    do script "cd '$ROOT' && ./scripts/start-wda.sh"
end tell
APPLESCRIPT
        echo "   → Attends que xcodebuild affiche « ServerURLHere-> »"
        echo ""
    else
        echo "   → Dans un autre terminal : cd $ROOT && ./scripts/start-wda.sh"
        echo ""
    fi

    if ! wait_for_wda 180; then
        echo ""
        echo "   ❌ WDA ne répond pas après 3 min."
        echo "   Vérifie le log dans logs/ ou relance start-wda.sh"
        echo ""
        echo "   Erreur fréquente : profil expiré (0xe8008011)"
        echo "   → Voir handoff/HANDOFF.md section « profil expire »"
        exit 1
    fi
fi
echo ""

# ── Étape 3 : App ─────────────────────────────────────────────
echo "🚀 Étape 3/3 — Dashboard"
echo ""
echo "   Sur ton iPhone : ouvre TikTok → onglet Accueil ▶ (feed)"
echo ""
read -r -p "   Appuie sur Entrée pour ouvrir le dashboard... "

exec "$ROOT/scripts/start-app.sh"
