# TikTok Control Center

Dashboard web pour lancer et monitorer les sessions de warmup.

## Lancer

```bash
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8080 --reload
```

Ouvrir http://127.0.0.1:8080

## API

| Endpoint | Méthode | Description |
|----------|---------|-------------|
| `/api/profiles` | GET | Liste des profils |
| `/api/sessions` | GET | Historique sessions |
| `/api/status` | GET | Session active ? |
| `/api/sessions/start` | POST | Démarrer warmup |
| `/api/sessions/stop` | POST | Arrêter warmup |
