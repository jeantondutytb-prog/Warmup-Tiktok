# TikTok Warmup Engine

Moteur Python d'automation iOS pour warmup TikTok via Appium.

## Commandes

```bash
python -m src.main --profile observer      # Lancer warmup
python -m src.main --profile light -d 20   # 20 minutes
python -m src.main --list-profiles         # Lister profils
python -m src.main --dry-run                 # Vérifier config
```

## Structure

- `src/behavior/` — Simulateur humain + actions TikTok
- `src/device/` — Connexion Appium iOS
- `src/session/` — Boucle de warmup
- `config/warmup_profiles.yaml` — Profils et probabilités
