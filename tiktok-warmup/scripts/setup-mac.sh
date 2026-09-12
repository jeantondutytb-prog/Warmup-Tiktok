#!/usr/bin/env bash
# Première installation sur Mac — une seule fois.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/lib.sh"
load_env

echo "=== Setup TikTok Warmup (Mac) ==="
echo ""

# Python venv
activate_venv
echo "✅ Python venv OK"

# .env
if [[ ! -f "$ROOT/.env" ]]; then
    cp "$ROOT/config/mac.env.example" "$ROOT/.env"
    echo "✅ Fichier .env créé"
else
    echo "ℹ️  .env existe déjà"
fi

# Auto-détection WDA
if found=$(find_wda_project); then
    if grep -q "^WDA_PROJECT=" "$ROOT/.env" 2>/dev/null; then
        sed -i '' "s|^WDA_PROJECT=.*|WDA_PROJECT=$found|" "$ROOT/.env"
    else
        echo "WDA_PROJECT=$found" >> "$ROOT/.env"
    fi
    echo "✅ WDA_PROJECT → $found"
else
    echo ""
    echo "⚠️  WebDriverAgent introuvable automatiquement."
    echo "   Lance : ./scripts/find-wda.sh"
    echo "   Ou installe Appium : npm install -g appium && appium driver install xcuitest"
fi

# Outils optionnels
echo ""
echo "Vérification des outils..."
for cmd in xcodebuild xcrun curl python3; do
    if command -v "$cmd" >/dev/null 2>&1; then
        echo "  ✅ $cmd"
    else
        echo "  ❌ $cmd manquant"
    fi
done

if ! command -v idevice_id >/dev/null 2>&1; then
    echo ""
    echo "💡 Pour détecter l'iPhone en USB, installe libimobiledevice :"
    echo "   brew install libimobiledevice"
fi

if [[ ! -d "$(dirname "$WDA_PROJECT")" ]] || [[ ! -f "$WDA_PROJECT" ]]; then
    echo ""
    echo "⚠️  WebDriverAgent introuvable — lance ./scripts/find-wda.sh"
fi

echo ""
echo "=== Setup terminé ==="
echo ""
echo "Prochaine étape :"
echo "  cd $ROOT"
echo "  ./scripts/lancer.sh"
