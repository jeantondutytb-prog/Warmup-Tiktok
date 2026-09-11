#!/usr/bin/env bash
# Terminal 1 — Lance WebDriverAgent sur l'iPhone branché.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck disable=SC1091
source "$ROOT/scripts/lib.sh"
load_env

echo "=== WebDriverAgent ==="
echo ""

if ! check_iphone; then
    echo "❌ Aucun iPhone détecté."
    echo "   → Branche l'iPhone en USB"
    echo "   → Déverrouille-le"
    echo "   → Accepte « Faire confiance à cet ordinateur »"
    exit 1
fi
echo "✅ iPhone détecté"

if [[ ! -f "$WDA_PROJECT" ]]; then
    echo "❌ Projet WDA introuvable : $WDA_PROJECT"
    echo "   Édite WDA_PROJECT dans .env ou lance ./scripts/setup-mac.sh"
    exit 1
fi

if url=$(detect_wda_url); then
    echo "✅ WDA tourne déjà : $url"
    echo ""
    echo "Tu peux lancer l'app dans un autre terminal :"
    echo "  cd $ROOT && ./scripts/lancer.sh"
    exit 0
fi

LOG="$ROOT/logs/wda-$(date +%Y%m%d-%H%M%S).log"
mkdir -p "$ROOT/logs"

echo "🚀 Démarrage xcodebuild (log : $LOG)"
echo "   Cherche « ServerURLHere-> » dans le log pour l'URL"
echo ""

xcodebuild test-without-building \
  -project "$WDA_PROJECT" \
  -scheme WebDriverAgentRunner \
  -derivedDataPath "$WDA_DERIVED_DATA" \
  -destination "id=$IPHONE_UDID" \
  -allowProvisioningUpdates \
  "IPHONEOS_DEPLOYMENT_TARGET=$IOS_DEPLOYMENT_TARGET" \
  "DEVELOPMENT_TEAM=$DEVELOPMENT_TEAM" \
  "CODE_SIGN_IDENTITY=Apple Development" \
  "PRODUCT_BUNDLE_IDENTIFIER=$WDA_BUNDLE_ID" \
  2>&1 | tee "$LOG"
