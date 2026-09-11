#!/usr/bin/env bash
# Fonctions partagées pour les scripts Mac.

set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

load_env() {
    if [[ -f "$ROOT/.env" ]]; then
        # shellcheck disable=SC1091
        set -a
        source "$ROOT/.env"
        set +a
    elif [[ -f "$ROOT/config/mac.env.example" ]]; then
        set -a
        source "$ROOT/config/mac.env.example"
        set +a
    fi

    : "${IPHONE_UDID:=00008020-000D0CE43A99002E}"
    : "${DEVELOPMENT_TEAM:=U284BGAVKL}"
    : "${WDA_BUNDLE_ID:=com.jean.wda.runner}"
    : "${IOS_DEPLOYMENT_TARGET:=18.7}"
    : "${WDA_PROJECT:=$HOME/.appium/node_modules/appium-xcuitest-driver/node_modules/appium-webdriveragent/WebDriverAgent.xcodeproj}"
    : "${WDA_DERIVED_DATA:=$HOME/Library/Developer/Xcode/DerivedData/WebDriverAgent-entqkdybqjzegiahlgkxvxghpzdf}"
    : "${WARMUP_PORT:=8000}"
}

check_iphone() {
    if xcrun devicectl list devices 2>/dev/null | grep -q "iPhone"; then
        return 0
    fi
    if command -v idevice_id >/dev/null 2>&1 && idevice_id -l 2>/dev/null | grep -q .; then
        return 0
    fi
    return 1
}

wda_ready() {
    local url="$1"
    curl -sf --max-time 2 "${url%/}/status" 2>/dev/null | grep -q '"ready":true'
}

detect_wda_url() {
    local candidates=(
        "${WDA_URL:-}"
        "http://127.0.0.1:8100"
        "http://localhost:8100"
        "http://169.254.140.1:8100"
    )

    for url in "${candidates[@]}"; do
        [[ -z "$url" ]] && continue
        if wda_ready "$url"; then
            echo "$url"
            return 0
        fi
    done
    return 1
}

wait_for_wda() {
    local max="${1:-120}"
    local i=0
    echo "⏳ Attente WebDriverAgent (max ${max}s)..."
    while (( i < max )); do
        if url=$(detect_wda_url); then
            echo "✅ WDA prêt : $url"
            export WDA_URL="$url"
            return 0
        fi
        sleep 2
        (( i += 2 ))
    done
    return 1
}

activate_venv() {
    if [[ ! -d "$ROOT/venv" ]]; then
        echo "📦 Création de l'environnement Python..."
        python3 -m venv "$ROOT/venv"
        # shellcheck disable=SC1091
        source "$ROOT/venv/bin/activate"
        pip install -q --upgrade pip
        pip install -q -r "$ROOT/requirements.txt"
    else
        # shellcheck disable=SC1091
        source "$ROOT/venv/bin/activate"
    fi
}
