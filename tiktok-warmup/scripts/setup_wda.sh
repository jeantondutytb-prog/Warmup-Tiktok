#!/usr/bin/env bash
# Setup WebDriverAgent pour automation iOS TikTok
# Prérequis: Xcode, compte Apple Developer, iPhone connecté en USB

set -euo pipefail

WDA_DIR="${HOME}/WebDriverAgent"
BUNDLE_ID="${WDA_BUNDLE_ID:-com.facebook.WebDriverAgentRunner}"

echo "=== Setup WebDriverAgent pour TikTok Warmup ==="

# 1. Outils iOS
if ! command -v idevice_id &>/dev/null; then
  echo "Installation libimobiledevice..."
  brew install libimobiledevice ios-deploy
fi

# 2. Appium
if ! command -v appium &>/dev/null; then
  echo "Installation Appium..."
  npm install -g appium
  appium driver install xcuitest
fi

# 3. WebDriverAgent
if [ ! -d "$WDA_DIR" ]; then
  echo "Clone WebDriverAgent..."
  git clone https://github.com/appium/WebDriverAgent.git "$WDA_DIR"
fi

UDID=$(idevice_id -l | head -1)
if [ -z "$UDID" ]; then
  echo "ERREUR: Aucun iPhone détecté. Branchez votre iPhone et faites 'Trust This Computer'."
  exit 1
fi

echo "iPhone détecté: $UDID"

# 4. Build WDA (nécessite signature Xcode)
echo ""
echo "=== Étape manuelle requise ==="
echo "1. Ouvrez Xcode: open ${WDA_DIR}/WebDriverAgent.xcodeproj"
echo "2. Sélectionnez WebDriverAgentRunner > Signing & Capabilities"
echo "3. Choisissez votre Team (Apple ID)"
echo "4. Changez le Bundle Identifier (ex: com.votrenom.WebDriverAgentRunner)"
echo "5. Connectez votre iPhone, sélectionnez-le comme destination"
echo "6. Product > Test (Cmd+U) — installe WDA sur l'iPhone"
echo ""
echo "Ensuite lancez:"
echo "  appium --relaxed-security"
echo "  cd tiktok-warmup && python -m src.main --profile observer"
