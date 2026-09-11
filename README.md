# Warmup TikTok

Outil de **warmup de comptes TikTok** sur **iPhone physique** connecté à un **Mac**, avec simulation de comportement humain via **Appium**.

## Architecture

```
Warmup-Tiktok/
├── tiktok-warmup/          # Moteur d'automation iOS
│   ├── config/             # Profils de warmup progressifs
│   ├── src/                # Code Python (Appium + simulateur humain)
│   └── scripts/            # Setup WebDriverAgent
└── tiktok-control-center/  # Dashboard web de contrôle
    ├── app/                # API FastAPI
    └── static/             # Interface web
```

## Prérequis (Mac)

| Outil | Usage |
|-------|-------|
| **Xcode** | Compiler WebDriverAgent sur l'iPhone |
| **Compte Apple Developer** | Signer WDA (gratuit avec Apple ID, ou payant) |
| **Homebrew** | Installer les dépendances |
| **Node.js 18+** | Appium server |
| **Python 3.11+** | Moteur de warmup |
| **iPhone USB** | Device cible avec TikTok installé |

## Installation rapide

### 1. Outils système

```bash
# libimobiledevice (détection iPhone USB)
brew install libimobiledevice ios-deploy

# Appium
npm install -g appium
appium driver install xcuitest

# Python
cd tiktok-warmup
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

### 2. WebDriverAgent (une seule fois)

```bash
chmod +x tiktok-warmup/scripts/setup_wda.sh
./tiktok-warmup/scripts/setup_wda.sh
```

Puis dans **Xcode** :
1. Ouvrir `~/WebDriverAgent/WebDriverAgent.xcodeproj`
2. WebDriverAgentRunner → Signing & Capabilities → choisir votre Team
3. Connecter l'iPhone, sélectionner comme destination
4. **Product → Test** (⌘U) pour installer WDA sur l'iPhone

### 3. Configurer `.env`

```bash
cd tiktok-warmup
cp .env.example .env
# Éditer IOS_PLATFORM_VERSION et IOS_UDID si besoin
```

Vérifier la détection iPhone :
```bash
idevice_id -l
```

## Utilisation

### Terminal (CLI)

```bash
# Terminal 1 — Appium
appium --relaxed-security

# Terminal 2 — Warmup (iPhone déverrouillé, TikTok peut être fermé)
cd tiktok-warmup
source .venv/bin/activate
python -m src.main --profile observer
```

### Dashboard web

```bash
# Terminal 1 — Appium (comme ci-dessus)

# Terminal 2 — Control Center
cd tiktok-control-center
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8080 --reload
```

Ouvrir http://127.0.0.1:8080 dans le navigateur.

## Profils de warmup

Progression recommandée avant de poster sur le compte :

| Profil | Période | Comportement |
|--------|---------|--------------|
| `observer` | Jours 1-3 | Scroll + visionnage uniquement |
| `light` | Jours 4-7 | + likes occasionnels (~8%) |
| `moderate` | Jours 8-14 | + follows, visites profil |
| `active` | Jour 15+ | Engagement naturel, prêt à poster |

```bash
python -m src.main --profile light --duration 20
python -m src.main --list-profiles
python -m src.main --dry-run
```

## Comportement humain simulé

- Durées de visionnage en **distribution gaussienne** (pas de timing fixe)
- Swipes avec **variance de vitesse et trajectoire**
- Pauses aléatoires (lecture commentaires, réflexion)
- Retours arrière occasionnels dans le feed
- Pauses entre sessions (3-8 min toutes les ~15 vidéos)
- Délais entre actions randomisés

## Logs

Chaque session génère un JSON dans `tiktok-warmup/logs/` :
- Vidéos vues, likes, follows, durée totale
- Historique action par action avec timestamps

## Workflow recommandé

1. **Jour 0** : Créer le compte TikTok manuellement sur l'iPhone
2. **Jours 1-3** : `observer` — 1-2 sessions/jour de 15 min
3. **Jours 4-7** : `light` — 2 sessions/jour
4. **Jours 8-14** : `moderate` — 2-3 sessions/jour
5. **Jour 15+** : `active` puis commencer à poster

> **Important** : Variez les horaires, utilisez le même réseau WiFi que d'habitude, et évitez les sessions trop longues d'un coup.

## Dépannage

| Problème | Solution |
|----------|----------|
| `Aucun iPhone détecté` | Câble USB, "Trust This Computer" sur l'iPhone |
| WDA timeout | Relancer Test dans Xcode, vérifier le signing |
| TikTok ne répond pas | UI TikTok change souvent — ajuster les sélecteurs dans `actions.py` |
| Appium connection refused | Vérifier `appium --relaxed-security` tourne sur port 4723 |

## Avertissement

Cet outil est destiné à automatiser des interactions sur **vos propres comptes**. L'utilisation de bots sur TikTok peut violer les [Conditions d'utilisation](https://www.tiktok.com/legal/terms-of-service). Utilisez à vos propres risques.
