#!/usr/bin/env bash
# Trouve WebDriverAgent.xcodeproj sur le Mac et met à jour .env
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/lib.sh"
load_env

echo "=== Recherche WebDriverAgent ==="
echo ""

path=$(find_wda_project || true)

if [[ -z "$path" ]]; then
    echo "❌ WebDriverAgent.xcodeproj introuvable."
    echo ""
    echo "Options :"
    echo ""
    echo "1) Tu l'as ouvert dans Xcode — dans Xcode :"
    echo "   Clic droit sur WebDriverAgent (barre gauche) → Show in Finder"
    echo "   Remonte d'un dossier et note le chemin complet."
    echo ""
    echo "2) Installe via Appium :"
    echo "   npm install -g appium"
    echo "   appium driver install xcuitest"
    echo "   Puis relance : ./scripts/find-wda.sh"
    echo ""
    echo "3) Clone manuellement :"
    echo "   git clone https://github.com/appium/WebDriverAgent.git ~/WebDriverAgent"
    echo "   Puis relance : ./scripts/find-wda.sh"
    exit 1
fi

echo "✅ Trouvé :"
echo "   $path"
echo ""

if [[ -f "$ROOT/.env" ]]; then
    if grep -q "^WDA_PROJECT=" "$ROOT/.env"; then
        # macOS sed
        sed -i '' "s|^WDA_PROJECT=.*|WDA_PROJECT=$path|" "$ROOT/.env"
    else
        echo "WDA_PROJECT=$path" >> "$ROOT/.env"
    fi
    echo "✅ .env mis à jour"
else
    cp "$ROOT/config/mac.env.example" "$ROOT/.env"
    sed -i '' "s|^WDA_PROJECT=.*|WDA_PROJECT=$path|" "$ROOT/.env"
    echo "✅ .env créé"
fi

echo ""
echo "Prochaine étape :"
echo "  ./scripts/start-wda.sh"
