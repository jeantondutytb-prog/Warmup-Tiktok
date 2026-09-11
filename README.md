# Warmup TikTok

Warmup automatisé de comptes TikTok sur **iPhone physique** (Mac + WebDriverAgent).

## Démarrage rapide (Mac)

```bash
git clone https://github.com/jeantondutytb-prog/Warmup-Tiktok.git
cd Warmup-Tiktok/tiktok-warmup

chmod +x scripts/*.sh
./scripts/setup-mac.sh    # une seule fois
./scripts/lancer.sh         # branche iPhone → ouvre http://localhost:8000
```

Sur l'iPhone : ouvre **TikTok → Accueil ▶ (feed)**, choisis le compte dans le dashboard, clique **Lancer le warmup**.

## Structure

| Dossier | Rôle |
|---------|------|
| `tiktok-warmup/` | Automation iPhone + dashboard (port 8000) |
| `tiktok-control-center/` | Grille Electron TikTok Web (warmup manuel) |

## Documentation

- **Guide complet** : [`tiktok-warmup/handoff/HANDOFF.md`](tiktok-warmup/handoff/HANDOFF.md)
- **Scripts Mac** : `tiktok-warmup/scripts/lancer.sh`
