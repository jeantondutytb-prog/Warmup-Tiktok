# TikTok Control Center — Design

**Date:** 2026-08-06
**Statut:** validé, prêt pour le plan d'implémentation

## Problème

Gérer plusieurs comptes TikTok depuis une seule fenêtre, en gardant les sessions
totalement cloisonnées, et en scrollant manuellement dans chacune. Aujourd'hui la
seule façon d'y arriver est de jongler entre des profils de navigateur séparés :
on perd la vue d'ensemble et on ne sait plus quel compte a été travaillé quand.

## Périmètre

L'application affiche des comptes et suit le temps passé dans chacun. Elle
n'exécute aucune action sur TikTok : pas de scroll automatique, pas de like, pas
d'abonnement, pas de commentaire. Toute interaction avec TikTok provient d'un
clic ou d'une frappe de l'utilisateur dans une cellule.

Cette limite est structurelle, pas une politique : aucun code d'émission
d'événements synthétiques vers une vue TikTok ne doit exister dans le projet.

## Contrainte technique déterminante

TikTok envoie `X-Frame-Options: DENY`, donc l'affichage en `<iframe>` est
impossible. Une mosaïque de vues TikTok live impose donc une application desktop
embarquant un vrai moteur Chromium. Il n'existe pas de version « site web » de ce
layout.

## Architecture

Application Electron, deux processus.

### Main process — propriétaire des sessions

Chaque compte possède une `Electron.Session` obtenue via
`session.fromPartition('persist:tt-<id>')`. Cette partition isole cookies,
localStorage, IndexedDB et cache. Deux comptes ne peuvent pas se voir.

Responsabilités du main :

- créer, détruire et recharger les `WebContentsView` ;
- appliquer la géométrie envoyée par le renderer ;
- forcer le user-agent par session ;
- appliquer le proxy par session quand il est configuré ;
- lire et écrire les fichiers de persistance.

### Renderer — l'UI de la grille

Le renderer ne contient aucune vue TikTok. Il affiche le châssis : en-têtes de
cellule, boutons d'action, chronos, barres de progression, panneau de notes. Il
calcule les rectangles de chaque cellule et les transmet au main par IPC ; le
main positionne les `WebContentsView` natives à ces coordonnées.

Le **châssis** remplit la fenêtre et ne scrolle pas. C'est ce qui garantit que la
position CSS d'une cellule et la position native de sa vue ne peuvent pas
diverger. Si le nombre de comptes dépasse la capacité de la grille, celle-ci
pagine — six cellules par page, navigation aux flèches ← / →.

À ne pas confondre avec le défilement **à l'intérieur** d'une cellule, qui est
l'interaction centrale de l'application : molette et clavier scrollent le fil
TikTok de la cellule focalisée, exactement comme dans un navigateur. Seul le
conteneur de la grille est fixe.

### Frontière IPC

Le renderer ne reçoit jamais de handle vers un `WebContents`. Les canaux exposés
via `contextBridge`, avec `contextIsolation` activé et `nodeIntegration`
désactivé :

| Canal | Sens | Charge utile |
| --- | --- | --- |
| `accounts:list` | R → M | — |
| `accounts:create` | R → M | `{ label, proxy?, userAgent? }` |
| `accounts:update` | R → M | `{ id, patch }` |
| `accounts:delete` | R → M | `{ id }` |
| `view:start` | R → M | `{ id }` |
| `view:stop` | R → M | `{ id }` |
| `view:reload` | R → M | `{ id }` |
| `layout:apply` | R → M | `{ focusedId, cells: [{ id, x, y, w, h }] }` |
| `view:state` | M → R | `{ id, status, url, title }` |
| `stats:tick` | M → R | `{ id, secondsToday }` |

## Modèle de données

Deux fichiers dans `app.getPath('userData')`, écrits par écriture atomique
(fichier temporaire puis `rename`).

### `accounts.json`

```jsonc
{
  "version": 1,
  "accounts": [
    {
      "id": "a7f3c1",           // opaque, stable, généré à la création
      "label": "@niche_cuisine",
      "partition": "persist:tt-a7f3c1",
      "proxy": null,             // ou { server, username, password }
      "userAgent": null,         // null = UA Chrome par défaut de l'app
      "notes": "",
      "dailyGoalMinutes": 15,
      "createdAt": "2026-08-06T12:00:00Z"
    }
  ]
}
```

`proxy` et `userAgent` sont présents dès la V1 et lus par le main au démarrage
d'une vue. La V1 ne fournit simplement pas d'UI pour les remplir ; les brancher
plus tard n'exige aucun changement d'architecture.

### `stats.json`

Séparé d'`accounts.json` pour qu'un tick de chrono ne réécrive pas la config.

```jsonc
{
  "version": 1,
  "days": {
    "2026-08-06": { "a7f3c1": 840, "b2e9d4": 120 }   // secondes
  }
}
```

Le fichier est écrit au plus une fois toutes les 30 secondes, et sur
`before-quit`. Les jours de plus de 90 jours sont purgés au démarrage.

## Comportement

### Cycle de vie d'un compte

1. L'utilisateur crée un compte en saisissant un libellé. Un `id` et une
   partition sont générés.
2. La cellule démarre sur `https://www.tiktok.com/`, déconnectée.
3. L'utilisateur se connecte à la main dans la cellule. La partition retient la
   session ; les lancements suivants sont déjà connectés.
4. Supprimer un compte détruit sa vue, retire son entrée d'`accounts.json` et
   efface les données de sa partition (`session.clearStorageData()`).

### Focus

Un clic sur une cellule lui donne le focus : elle s'agrandit, les autres se
réduisent. Le renderer recalcule la géométrie et émet `layout:apply`. La cellule
focalisée est la seule dans laquelle on scrolle.

### Chrono

Le temps ne s'accumule que pour la cellule focalisée, et seulement quand la
fenêtre de l'application est au premier plan. Perdre le focus applicatif met le
chrono en pause — sinon une fenêtre laissée ouverte fausse totalement les
chiffres. Un tick d'une seconde alimente `stats.json`.

### État d'une vue

`status` vaut `stopped`, `loading`, `ready` ou `error`. Il dérive des événements
`did-start-loading`, `did-finish-load` et `did-fail-load` du `WebContents`. Une
erreur affiche le code et un bouton « recharger » dans l'en-tête de la cellule ;
elle ne fait jamais tomber les autres cellules.

## Points durs

### User-agent

Le Chromium d'Electron annonce `Electron/<version>` dans son user-agent, ce que
TikTok rejette. Le main appelle `session.setUserAgent()` avec une chaîne Chrome
stable avant tout chargement. C'est un correctif obligatoire, pas une option.

### Charge CPU

Plusieurs lecteurs vidéo simultanés saturent la machine. Une cellule non
focalisée est mise en sourdine et sa lecture suspendue ; seule la cellule active
joue. La suspension se fait en injectant, dans la vue, un script qui met en pause
les éléments `<video>` — c'est un contrôle de lecture média, pas une action sur
le compte TikTok.

### Connexion et captcha

TikTok peut présenter un captcha à la connexion. Il se résout normalement dans la
cellule, mais c'est le point de rupture le plus probable du projet.

**Conséquence sur l'ordre d'implémentation :** la toute première étape est un
prototype jetable — une fenêtre, une `WebContentsView`, un UA forcé — servant
uniquement à vérifier qu'on peut se connecter à un compte TikTok et lire le fil.
Rien d'autre n'est construit avant que cette vérification passe.

## Tests

La logique pure est isolée du code Electron dans des modules sans import
`electron`, et testée en unitaire :

- calcul de la géométrie de grille (N comptes, une cellule focalisée, dimensions
  de fenêtre → liste de rectangles) ;
- agrégation des temps (ticks → totaux journaliers, changement de jour, purge) ;
- CRUD des comptes et migrations de schéma (`version`).

L'intégration Electron — chargement réel de TikTok, isolation effective des
partitions, application du proxy — se vérifie à la main, sur des comptes réels.
L'isolation se contrôle en se connectant à deux comptes et en vérifiant que
chaque cellule affiche bien le sien après redémarrage.

## Hors périmètre V1

- UI de configuration des proxies (le champ existe et est lu ; pas d'écran).
- Empreinte navigateur par compte (canvas, timezone, résolution).
- Navigation groupée vers une même URL sur plusieurs comptes.
- Publication, statistiques TikTok, ou toute lecture de l'API TikTok.
- Toute forme d'action automatisée sur un compte.
