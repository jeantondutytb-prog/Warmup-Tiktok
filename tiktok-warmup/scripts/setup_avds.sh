#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

if ! command -v avdmanager &>/dev/null; then
    echo "Error: avdmanager not found. Install Android SDK command-line tools."
    echo "  brew install --cask android-commandlinetools"
    echo "  sdkmanager 'platform-tools' 'platforms;android-34' 'system-images;android-34;google_apis;arm64-v8a'"
    exit 1
fi

SYSTEM_IMAGE="system-images;android-34;google_apis_playstore;arm64-v8a"

echo "Checking system image..."
if ! sdkmanager --list_installed 2>/dev/null | grep -q "$SYSTEM_IMAGE"; then
    echo "Installing system image..."
    sdkmanager "$SYSTEM_IMAGE"
fi

AVDS="avd_compte1:pixel_6 avd_compte2:pixel_4 avd_compte3:pixel_3a avd_compte4:pixel_5 avd_compte5:pixel_7"

for entry in $AVDS; do
    avd_name="${entry%%:*}"
    device="${entry##*:}"
    if avdmanager list avd 2>/dev/null | grep -q "$avd_name"; then
        echo "AVD $avd_name already exists, skipping."
    else
        echo "Creating AVD: $avd_name (device=$device)..."
        echo "no" | avdmanager create avd \
            -n "$avd_name" \
            -k "$SYSTEM_IMAGE" \
            -d "$device" \
            --force
        echo "Created $avd_name"
    fi
done

echo ""
echo "All AVDs created. Start them with:"
echo "  emulator -avd avd_compte1 -no-snapshot -no-audio &"
echo ""
echo "Then start Appium:"
echo "  appium --port 4723"
echo ""
echo "Then start the app:"
echo "  cd $PROJECT_DIR && source venv/bin/activate && python -m app.main"
