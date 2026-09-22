# TikTok Warmup — Handoff

**Dernière mise à jour : 22.09.2026** — cockpit sur Vercel, agent unique sur le Mac.

## Ce que fait l'app

Warmup de comptes TikTok sur un **iPhone XS physique branché en USB**, piloté
par WebDriverAgent. L'app exécute le **Protocole Peachtint** : des sessions de
18 minutes en cinq phases, sous des plafonds d'action volontairement bas.

Le **dashboard** vit sur Vercel (`tiktok-warmup/web`). Le Mac ne lance plus
FastAPI + xcodebuild à la main : un seul process (`python -m agent`) détecte
l'iPhone, démarre WDA, et exécute les Start/Stop envoyés depuis le site.

Vercel ne peut pas parler à un iPhone USB. D'où la coupure :

```
Dashboard Vercel  --jobs-->  agent Mac  --WDA-->  iPhone
       ^                        |
       +------- snapshot/events -+
```

> Le document source dit que le protocole est prévu pour être exécuté à la
> main, et que l'engagement automatisé sur plusieurs comptes est le motif que
> TikTok détecte le mieux. L'app l'automatise quand même — c'est un choix
> assumé. En contrepartie elle applique des garde-fous que l'ancienne boucle
> n'avait pas : plafonds sur 24 h glissantes, débit horaire, espacement entre
> comptes, refus de taper un point non calibré.

## Stack

- **Dashboard** : Next.js 15 sur Vercel, état dans Vercel Blob
- **Agent Mac** : `python -m agent` — WDA + orchestrateur + pont HTTP
- **Python 3.14**, venv dans `venv/`
- **SQLAlchemy** / SQLite local (`db/warmup.db`) — le protocole reste sur le Mac
- **WebDriverAgent** en direct. L'agent lit `ServerURLHere->` tout seul.

Le dashboard FastAPI local (`python -m app.main`, port 8000) existe encore
pour le debug, mais ce n'est plus le chemin normal.

## Lancer — le chemin normal

1. Une fois : copier `.env.agent.example` → `.env.agent`, coller `WARMUP_URL`
   et le même `AGENT_TOKEN` que sur Vercel.
2. Brancher l'iPhone en USB, le déverrouiller.
3. Sur le Mac :

```bash
cd /Users/jean/tiktok-warmup   # ou le clone Warmup-Tiktok/tiktok-warmup
source venv/bin/activate
python -m agent
# équivalent : ./scripts/warmup
```

4. Ouvrir le dashboard Vercel, entrer le mot de passe, cliquer **Start**.

Pour ne plus jamais relancer l'agent à la main :

```bash
python -m agent install
launchctl load ~/Library/LaunchAgents/com.peachtint.warmup.plist
```

Ensuite : brancher l'iPhone → ouvrir le site → Start.

### Ancien lancement (deux terminaux, localhost)

```bash
# Terminal 1 : WebDriverAgent (voir « L'adresse de WDA change » plus bas)
xcodebuild test-without-building \
  -project /Users/jean/.appium/node_modules/appium-xcuitest-driver/node_modules/appium-webdriveragent/WebDriverAgent.xcodeproj \
  -scheme WebDriverAgentRunner \
  -derivedDataPath /Users/jean/Library/Developer/Xcode/DerivedData/WebDriverAgent-entqkdybqjzegiahlgkxvxghpzdf \
  -destination id=00008020-000D0CE43A99002E -allowProvisioningUpdates \
  IPHONEOS_DEPLOYMENT_TARGET=18.7 DEVELOPMENT_TEAM=U284BGAVKL \
  CODE_SIGN_IDENTITY="Apple Development" PRODUCT_BUNDLE_IDENTIFIER=com.jean.wda.runner

# Terminal 2 : l'app
cd /Users/jean/tiktok-warmup
source venv/bin/activate
WDA_URL=http://192.168.1.61:8100 python -m app.main
```

Dashboard local : `http://localhost:8000`.

## Calibration — faite le 03.09.2026

Les huit repères utilisés par les quatre phases ont été **vérifiés par un tap
réel** dont l'effet a été constaté sur une capture. Preuves dans
`calibration/`. Compte de test : emma.srpt, iOS 18.7.7, TikTok en français.

L'app refuse de démarrer si l'un d'eux repasse à `calibrated: false`. La garde
ne regarde que `REQUIRED_POINTS` (dans `orchestrator.py`) : les repères
inutilisés — partage, commentaire, sélecteur de compte — ne bloquent rien.

### ⚠️ Les valeurs d'août étaient toutes fausses

TikTok a ajouté un bouton de réaction (smiley) en haut de la barre latérale,
ce qui a décalé tout le reste d'environ 140 points vers le bas :

| Repère | Valeur d'août | Réel | Ce que tapait l'ancienne valeur |
|---|---|---|---|
| `btn_like` | 0.907, 0.345 | **0.920, 0.517** | le smiley de réaction |
| `btn_follow` | 0.907, 0.298 | 0.920, 0.458 | du vide |
| `btn_comment` | 0.907, 0.400 | 0.920, 0.597 | le haut de l'avatar |
| `btn_share` | 0.907, 0.493 | 0.918, 0.764 | du vide |
| `home_tab` | 0.10, 0.97 | **0.099, 0.926** | la bande du trait d'accueil |

`tests/test_coords.py` échoue si `btn_like` remonte au-dessus de 0.45.

### Recalibrer après une mise à jour de TikTok

```bash
python -m scripts.calibrate list                 # état de tous les points
python -m scripts.calibrate probe search_icon    # capture, tape, recapture
python -m scripts.calibrate set search_icon 0.925 0.080
python -m scripts.calibrate pixel 1035 186       # pixels d'une capture → pourcentages
```

`probe` écrit un avant/après dans `calibration/` : ouvre les deux images pour
voir où le tap a atterri.

## iPhone XS

- **Écran** : 375x812 points, rétine 3x (1124x2436 pixels)
- **UDID** : `00008020-000D0CE43A99002E`
- **WDA Bundle** : `com.jean.wda.runner` · **Team** : `U284BGAVKL`

### Le profil de provisionnement expire tous les 7 jours

C'est la limite du compte développeur gratuit. Quand WDA refuse de
s'installer avec `0xe8008011 (This provisioning profile has expired)` :

```bash
cd /Users/jean/.appium/node_modules/appium-xcuitest-driver/node_modules/appium-webdriveragent
xcodebuild build-for-testing -project WebDriverAgent.xcodeproj \
  -scheme WebDriverAgentRunner \
  -derivedDataPath /Users/jean/Library/Developer/Xcode/DerivedData/WebDriverAgent-entqkdybqjzegiahlgkxvxghpzdf \
  -destination id=00008020-000D0CE43A99002E -allowProvisioningUpdates \
  IPHONEOS_DEPLOYMENT_TARGET=18.7 DEVELOPMENT_TEAM=U284BGAVKL \
  CODE_SIGN_IDENTITY="Apple Development" PRODUCT_BUNDLE_IDENTIFIER=com.jean.wda.runner
```

`-allowProvisioningUpdates` régénère le profil sans passer par Xcode.
Régénéré le 03.09, **valide jusqu'au 10.09.2026**.

### L'adresse de WDA change

WDA annonce son adresse au démarrage — cherche `ServerURLHere->` dans le log
xcodebuild. Le 03.09 il écoutait sur **192.168.1.61:8100** (Wi-Fi), pas sur le
`169.254.140.1` du lien USB d'août. D'où :

```bash
WDA_URL=http://192.168.1.61:8100 python -m app.main
```

L'UI de TikTok n'est **pas** exposée dans l'arbre d'accessibilité XCUITest
(tout est `visible="false"`, sans label). D'où le tap en coordonnées partout,
et `config/coords.yaml` comme source unique de vérité.

## Les 4 comptes

| Compte | Rôle | Traitement |
|---|---|---|
| `emma.srpt` | vaisseau amiral peachtint | warmup |
| `chloe.rtps` | second couteau | warmup — **renommer le 25.09**, aucune publication peachtint avant |
| `eva.drtp` | labo | tests de hooks risqués |
| `emma.ftpl` | Capiria, coupes hommes | **`protected: true`** — aucune session, pas de bouton Start |

`protected` vient de `config/accounts.yaml`, qui fait foi à chaque démarrage :
le retirer est un geste explicite.

## La session de 18 minutes

| Phase | Fenêtre | Ce qui se passe |
|---|---|---|
| `fyp_entry` | 0–2′ | 3–4 vidéos du fil, en entier, même hors niche |
| `search` | 2–10′ | **un seul** mot-clé, vidéos en entier, ~1 like sur 3 |
| `profiles` | 10–13′ | 2–3 profils, grille scrollée, 1–2 vidéos ouvertes |
| `fyp_measure` | 13–18′ | 20 scrolls capturés dans `db/fyp/<session_id>/` |

**Le replay est le signal le plus fort du protocole**, devant la vue complète.
`watch_fully()` laisse donc boucler une deuxième fois toute vidéo de moins de
15 secondes.

Le mot-clé tourne d'une session à l'autre (`config/keywords.yaml`, 5 FR + 5 EN).
Enchaîner la liste dans une même session est exactement ce que le protocole
interdit.

## Plafonds appliqués

Fenêtre **24 h glissantes**, pas calendaire — minuit ne remet rien à zéro côté
TikTok. La fourchette est retirée au sort à chaque session : un plafond
constant est lui-même un motif.

| Action | Plafond 24 h |
|---|---|
| Abonnements | 10–15, et ≤ 5/h |
| Likes | 20–30 |
| Commentaires | 0–3 |

Par session : **3 abonnements max**, **jamais deux d'affilée**, 3 profils max.

## Cadence

- 2 sessions/jour pendant 7 jours, puis 1/jour en entretien
- **≥ 4 h** entre deux sessions d'un même compte
- **≥ 30 min** entre deux comptes sur le même appareil

Le refus est explicite et remonte au dashboard (événement SSE `refused`) plutôt
que d'attendre en silence.

## La mesure FYP — la seule partie manuelle

Le protocole demande de compter les vidéos « de la niche » sur 20 scrolls.
Reconnaître une niche sur une capture n'est pas fiable sans OCR, et aucun OCR
n'est installé ici. L'app ne devine donc pas : elle **enregistre les 20
captures** et attend ton comptage.

```bash
curl localhost:8000/api/fyp/pending
curl -X POST localhost:8000/api/fyp/12 -d '{"count": 3}' -H 'Content-Type: application/json'
```

Verdict dérivé : **0–1 = cold** (le warmup n'a pas pris) · **2 = warming** ·
**3+ = ready** (passage en entretien possible).

## Faire avancer le protocole

```bash
curl -X POST localhost:8000/api/protocol-day/emma.srpt -d '{"day": 4}' -H 'Content-Type: application/json'
```

Le jour 8 fait basculer le compte à une session par jour.

## Architecture

```
web/                  - dashboard Next.js déployé sur Vercel
agent/                - pont Mac : WDA + jobs Vercel + orchestrateur
app/
  core/
    protocol.py       - LE protocole en logique pure : phases, plafonds,
                        cadence, rotation de mots-clés. Aucun import Appium,
                        testable sans iPhone. C'est ici qu'on change les règles.
    coords.py         - charge config/coords.yaml, refuse les points non calibrés
    orchestrator.py   - déroule les 5 phases, tient le budget, journalise
    action_engine.py  - les gestes : watch_fully, open_search, browse_profile_grid…
    anti_detect.py    - timings gaussiens, micro-pauses, variation de commentaires
    appium_driver.py  - session WDA en direct, URL via WDA_URL
  models/models.py    - Account, WarmupSession, ActionLog + `migrate()`
  api/routes.py       - statut, start/stop, SSE, saisie FYP, jour de protocole
config/
  accounts.yaml       - les 4 comptes, rôle et protection
  keywords.yaml       - 5 mots-clés FR + 5 EN
  coords.yaml         - tous les points de tap, en % d'écran
scripts/calibrate.py  - l'outil de calibration
scripts/warmup        - alias de `python -m agent`
```

## Base de données

`migrate()` ajoute au démarrage les colonnes que `create_all` ne peut pas créer
sur une table SQLite existante : `accounts.protocol_day/role/protected` et
`sessions.keyword/fyp_niche_count/fyp_verdict/completed`.

Les 4 anciens comptes (`jeanzdozzr`, `comptoxltmg`, `ambrezsgs0i`,
`alicevuum5e`) et leurs 8175 lignes de log restent en base mais ne sont plus
dans `accounts.yaml`, donc invisibles au dashboard.

Sauvegarde du 03.09 : `/tmp/warmup-backup-20260903.db`.

## Tests

```bash
python -m pytest tests/ -q      # 89 tests
```

Toujours scoper à `tests/`. À la racine traînent des `test_*.py` de débogage du
21 août qui appellent `exit(1)` à l'import et font planter la collecte pytest.

## Leçons de la session #42 (03.09, première session réelle)

**La session a rapporté 9 likes et 2 abonnements. Le compte n'en a reçu
aucun.** Vérifié sur l'appareil : `Suivis` est resté à 61 (le +1 venait de la
calibration) et la vidéo la plus récente de l'onglet « J'aime » datait de la
calibration. Cinq défauts, tous corrigés et couverts par des tests.

### Les deux causes racines

**`like_video` tapait une constante d'août codée en dur.** `BTN_LIKE_X/Y =
340, 280` vivait en haut de `action_engine.py` et court-circuitait entièrement
`coords.yaml`. Recalibrer le fichier n'avait donc aucun effet sur les likes.
Toutes les constantes sont supprimées : `coords.yaml` est la seule source.

**L'ordre des onglets d'une page de résultats dépend de la requête.** Pour
« filtre digicam » : `Demander · Top · Vidéos · Utilisateurs · Boutique`. Pour
« filtre pellicule » : `Demander · Top · **Boutique** · Vidéos · Utilisateurs`.
Le `tab_videos` fixé à x=0.509 est tombé sur « Boutique » et la phase recherche
s'est déroulée dans TikTok Shop, sur une page « Produit indisponible ». Aucune
coordonnée fixe ne peut désigner « Vidéos » : le tap d'onglet est supprimé, on
reste sur « Top » (sélectionné par défaut, et rempli de vidéos).

### Aucune action n'était vérifiée

C'est ce qui a rendu les deux causes invisibles pendant toute la session : un
tap qui rate ne lève aucune exception, donc l'app rapportait un succès.

- `like_video` lit désormais la couleur du cœur avant et après le tap, et
  distingue trois cas : like réel, tap manqué, retrait d'un like existant.
- La phase de recherche **abandonne après 2 likes manqués d'affilée**
  (`MISSED_LIKES_BEFORE_ABORT`). Deux ratés ne sont pas de la malchance : ils
  veulent dire qu'on n'est pas sur une vidéo.

> Deux heuristiques par pixels ont été essayées pour reconnaître un écran
> vidéo (luminance moyenne, puis présence du cœur) et **toutes deux échouent**
> sur les captures réelles : un fond blanc (Boutique, clavier) et une grille
> de vignettes sombres ne se séparent pas proprement. Le signal retenu est
> comportemental — est-ce que le like a pris ? — et non visuel.

### Vérifié sur l'appareil le 04.09

Chaque correctif a été rejoué sur l'iPhone, avec constat visuel ou compteur à
l'appui — pas sur la seule foi de ce que le code renvoie :

| Correctif | Preuve |
|---|---|
| Recherche sans tap d'onglet | ouvre bien une vidéo, plus la Boutique |
| `like_video` recalibré + vérifié | cœur passé au rouge, 147 likes |
| `follow_from_profile` vérifié | **Suivis 61 → 62** sur emma.srpt |
| Refus du 2ᵉ abonnement | « pas de bouton d'abonnement ici », **sans taper** — c'est ce qui empêche d'ouvrir une conversation privée |
| `return_to_feed` | clavier refermé, retour sur « Pour toi » |

Observé au passage : le **premier** tap de like après l'ouverture d'une vidéo
peut se perdre pendant le chargement. `like_video` fait donc **une** reprise
avant de déclarer un raté, sans quoi deux chargements lents de suite feraient
abandonner la phase pour rien.

### Les trois défauts secondaires

**`home_tab` ne ramène pas au fil depuis une vidéo.** Sur une vidéo ouverte
depuis la recherche ou un profil, la barre du bas n'est pas la barre d'onglets
mais le champ « Ajouter un commentaire » — au même endroit. Le tap ouvrait le
clavier, et la phase de mesure a tourné 90 secondes dessus avant l'arrêt.
Remplacé par `return_to_feed()`, qui relance l'app (seul retour déterministe :
TikTok rouvre toujours sur le fil) puis vérifie que le clavier est retombé, en
mesurant la luminosité du bas de l'écran.

**Un refus était journalisé comme l'action refusée.** « SKIP — jamais deux
abonnements d'affilée » entrait dans `action_logs` en tant que `follow`, donc
comptait dans le plafond 24 h. `_record` filtre désormais tout détail
commençant par `SKIP` et le diffuse en événement `refused`.

**Une session annulée était marquée `completed: True`.** `stop_all` annule la
tâche, et la `CancelledError` sautait par-dessus l'affectation. Rattrapée
explicitement.

## Réserves connues

- **La phase profils ne revient pas au fil entre deux profils.** Après un
  abonnement on reste sur le profil du créateur ; le tap suivant sur
  `creator_avatar` n'ouvre donc rien de neuf. Pire, sur un profil déjà suivi
  le bouton « Suivre » devient « Message » à la même position — un abonnement
  y ouvrirait une conversation privée. Lors de la session #42 c'est la règle
  « jamais deux abonnements d'affilée » qui a évité le mauvais tap, par
  chance. **À corriger** : intercaler un `return_to_feed()` entre deux
  itérations de `_phase_profiles`.
- **`go_back` n'est pas toujours terminé** quand la vignette suivante est
  tapée dans `browse_profile_grid`. Le tap atterrit alors sur le corps de la
  vidéo et la met en pause au lieu d'ouvrir une nouvelle vidéo. Sans
  conséquence, mais une vidéo de moins est vue. Corriger demanderait une
  détection d'état d'écran.
- **`profile_grid_cell` vise le centre de la grille**, pas « la première
  cellule » : la hauteur d'en-tête d'un profil varie avec la bio, les stories
  à la une, et le panneau de suggestions qui apparaît **après** un abonnement.
  C'est pourquoi les phases parcourent la grille **avant** de s'abonner.
- **Le pseudo réel d'emma.srpt est `@emma.srtp`** (lettres inversées), alors
  que le nom affiché est `emma.srpt`. `accounts.yaml` utilise `emma.srpt`,
  qui n'est qu'un libellé côté base — mais à trancher avant de communiquer
  dessus.

## Ce qui n'est pas fait

- **Republier / Partager** — demandés, jamais construits. Le partage est le
  plus fort des signaux actifs selon le protocole, donc c'est le meilleur
  candidat suivant.
- **Comptage FYP automatique** — demanderait un OCR (Vision via pyobjc, ou
  tesseract). Rien d'installé aujourd'hui.
- **Les commentaires** — le protocole en autorise 0-3/24h, aucune phase n'en
  poste. `btn_comment` est mesuré mais jamais vérifié par un tap.
- **Le plan J1–J14, le relevé de métriques par vidéo et les 5 accroches** du
  document Peachtint : hors app, pas commencés.

## Historique des correctifs

| Problème | Correctif |
|---|---|
| Certificat WDA non fiable après redémarrage | Re-valider dans Réglages > Général > VPN et gestion d'appareil |
| Tap du sélecteur de compte à y=7% | Atterrissait dans l'encoche. Passé à y=16% |
| Modale TikTok invisible à l'accessibilité | Bascule sur le tap en coordonnées |
| Fenêtre d'activité bloquante à 23h | `hour_end` passé de 23 à 24 |
| Comportement « robotique » | Flux naturel : scroll→watch→peut-être interagir |
| Visionnages trop longs | Pondération 50% 2-4s, 30% 5-10s, 15% 10-20s, 5% 20-35s |
| Bascule de compte auto peu fiable | Switch manuel |
| `start_time` indéfini dans `_do_action` | Corrigé : dérivé de `ws.started_at` |
| Tests désalignés après le rewrite du 21.08 | Fourchettes et pilote WDA remis à jour |
| `find_element` bloque sur le champ de recherche | Frappe via `/wda/keys` sur le champ auto-focalisé |
| Abonnement depuis un profil tapait le + de la barre latérale | `follow_from_profile` tape le bouton « Suivre » |
| Barre latérale décalée par le nouveau bouton smiley | Tous les repères recalibrés le 03.09 |
