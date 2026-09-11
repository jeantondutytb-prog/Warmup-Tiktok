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
    echo "✅ Fichier .env créé — édite-le si tes chemins diffèrent"
else
    echo "ℹ️  .env existe déjà"
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

if [[ ! -d "$(dirname "$WDA_PROJECT")" ]]; then
    echo ""
    echo "⚠️  WebDriverAgent introuvable à :"
    echo "   $WDA_PROJECT"
    echo ""
    echo "Installe Appium + driver XCUITest :"
    echo "   npm install -g appium"
    echo "   appium driver install xcuitest"
    echo ""
    echo "Puis mets à jour WDA_PROJECT dans .env"
fi

echo ""
echo "=== Setup terminé ==="
echo ""
echo "Prochaine étape :"
echo "  cd $ROOT"
echo "  ./scripts/lancer.sh"
