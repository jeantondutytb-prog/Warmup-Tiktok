# TikTok Control Center Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Une application Electron affichant plusieurs comptes TikTok en mosaïque, chacun dans une session totalement isolée, dans laquelle l'utilisateur scrolle à la main.

**Architecture:** Un `BaseWindow` contient une `WebContentsView` de châssis (l'UI de la grille) couvrant la fenêtre, et une `WebContentsView` par compte posée par-dessus aux coordonnées calculées par le renderer. Chaque vue de compte utilise une partition `persist:tt-<id>`, ce qui cloisonne cookies et stockage. Toute la logique calculable (géométrie, temps, comptes) vit dans `src/core/` sans aucun import Electron, et est testée en unitaire.

**Tech Stack:** Electron 43.3.0, TypeScript 7.0.2, Vitest 4.1.10, pnpm. Pas de bundler, pas de framework UI — HTML/CSS/TS compilés par `tsc`.

## Global Constraints

- Electron `43.3.0`, TypeScript `7.0.2`, Vitest `4.1.10`, gestionnaire de paquets `pnpm`.
- `src/core/**` ne doit **jamais** importer `electron`. C'est ce qui rend ces modules testables sans lancer d'application.
- Toute fenêtre créée utilise `contextIsolation: true` et `nodeIntegration: false`.
- Le renderer ne reçoit jamais de référence à un `WebContents`. Il ne communique que par les canaux IPC listés en Task 9.
- **Aucun code n'envoie d'événement d'entrée synthétique à une vue de compte.** `sendInputEvent`, les clics programmés, les frappes simulées et le défilement programmé vers une vue TikTok sont interdits. La seule injection autorisée dans une vue de compte est la mise en pause des éléments `<video>` (Task 8), qui est un contrôle de lecture média local.
- Les fichiers JSON sont écrits atomiquement : fichier temporaire puis `rename`.
- Les modules du renderer utilisent des imports ESM avec extension `.js` explicite (`import { computeLayout } from '../core/layout.js'`), car le navigateur ne résout pas les extensions.

---

### Task 1: Prototype jetable — vérifier que TikTok se charge et se connecte

Le spec impose cette étape en premier. Le captcha de connexion TikTok est le point de rupture le plus probable du projet ; on le teste avant de construire quoi que ce soit d'autre. Ce code est **jeté** à la fin de la tâche.

**Files:**
- Create: `proto/main.js` (supprimé en fin de tâche)
- Create: `package.json`

**Interfaces:**
- Consumes: rien
- Produces: rien (code jetable). Produit une **décision** : le projet continue, ou l'approche Electron est abandonnée.

- [ ] **Step 1: Initialiser le projet et installer Electron**

```bash
cd /Users/jean/tiktok-control-center
pnpm init
pnpm add -D electron@43.3.0
```

- [ ] **Step 2: Écrire le prototype**

Créer `proto/main.js` :

```javascript
const { app, BaseWindow, WebContentsView, session } = require('electron')

// Le Chromium d'Electron annonce "Electron/43.3.0" et le nom de l'app dans son
// user-agent, ce que TikTok rejette. On retire ces deux jetons pour retrouver
// un user-agent Chrome authentique correspondant au Chromium embarqué.
function stripElectronTokens (ua) {
  return ua
    .replace(/\s?Electron\/\S+/, '')
    .replace(new RegExp(`\\s?${app.getName()}\\/\\S+`), '')
    .trim()
}

app.whenReady().then(() => {
  const ses = session.fromPartition('persist:proto')
  const ua = stripElectronTokens(ses.getUserAgent())
  console.log('UA original :', ses.getUserAgent())
  console.log('UA envoyé   :', ua)
  ses.setUserAgent(ua)

  const win = new BaseWindow({ width: 1200, height: 900 })
  const view = new WebContentsView({
    webPreferences: { partition: 'persist:proto' }
  })
  win.contentView.addChildView(view)
  view.setBounds({ x: 0, y: 0, width: 1200, height: 900 })
  view.webContents.loadURL('https://www.tiktok.com/')
})

app.on('window-all-closed', () => app.quit())
```

- [ ] **Step 3: Lancer et vérifier à la main**

```bash
pnpm exec electron proto/main.js
```

Vérifier, dans l'ordre :

1. La page TikTok s'affiche (pas de « navigateur non supporté »).
2. Le fil défile à la molette.
3. Une vidéo se lit et le son fonctionne.
4. La connexion à un vrai compte aboutit — c'est le point critique. Si un captcha apparaît, vérifier qu'il est résolvable dans la fenêtre.
5. Quitter, relancer : la session doit être **toujours connectée** (c'est la preuve que `persist:` fonctionne).

- [ ] **Step 4: Décision — porte du projet**

Si l'étape 4 ou 5 échoue, **s'arrêter ici** et remonter le blocage. Le reste du plan suppose que ces cinq points passent. Ne pas contourner un échec de connexion en simulant des entrées : c'est explicitement hors périmètre.

- [ ] **Step 5: Supprimer le prototype et committer**

```bash
rm -rf proto
printf 'node_modules/\ndist/\n' > .gitignore
git add .gitignore package.json pnpm-lock.yaml
git commit -m "chore: init project, validate TikTok loads in Electron"
```

---

### Task 2: Scaffolding TypeScript, Vitest et types partagés

**Files:**
- Create: `tsconfig.json`
- Create: `tsconfig.renderer.json`
- Create: `vitest.config.ts`
- Create: `src/core/types.ts`
- Modify: `package.json`

**Interfaces:**
- Consumes: rien
- Produces: les types `Proxy`, `Account`, `AccountsFile`, `StatsFile`, `Rect`, `CellRect`, `ViewStatus`, tous importés par les tâches suivantes. La constante `PAGE_SIZE = 6`.

- [ ] **Step 1: Installer les outils**

```bash
pnpm add -D typescript@7.0.2 vitest@4.1.10 @types/node
```

- [ ] **Step 2: Écrire les tsconfig**

`tsconfig.json` — compile le main, le preload et le core en CommonJS vers `dist/` :

```json
{
  "compilerOptions": {
    "target": "ES2022",
    // TypeScript 7 a supprime `moduleResolution: "node"`, et impose que
    // `module` et `moduleResolution` forment une paire Node16 coherente.
    // L'emission reste du CommonJS parce que package.json n'a pas
    // `"type": "module"` — contrainte globale, a ne jamais reintroduire.
    "module": "Node16",
    "moduleResolution": "node16",
    "outDir": "dist",
    "rootDir": "src",
    "strict": true,
    "esModuleInterop": true,
    "skipLibCheck": true,
    "sourceMap": true
  },
  "include": ["src/main/**/*", "src/preload/**/*", "src/core/**/*"]
}
```

`tsconfig.renderer.json` — compile le renderer et le core en ESM vers `dist/renderer/` :

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "esnext",
    "moduleResolution": "bundler",
    "outDir": "dist/renderer",
    "rootDir": "src",
    "strict": true,
    "skipLibCheck": true,
    "sourceMap": true,
    "lib": ["ES2022", "DOM"]
  },
  "include": ["src/renderer/**/*", "src/core/**/*"]
}
```

`src/core/` est volontairement compilé par les deux : le main l'utilise en CommonJS, le renderer en ESM. C'est ce qui évite d'introduire un bundler.

- [ ] **Step 3: Écrire la config Vitest**

`vitest.config.ts` :

```typescript
import { defineConfig } from 'vitest/config'

export default defineConfig({
  test: {
    include: ['tests/**/*.test.ts'],
    environment: 'node',
    // Vitest 4 sort en echec quand aucun fichier de test n'existe. Necessaire
    // pour que l'echafaudage passe ; sans effet des la Task 3.
    passWithNoTests: true
  }
})
```

- [ ] **Step 4: Écrire les types partagés**

`src/core/types.ts` :

```typescript
export const PAGE_SIZE = 6

export interface Proxy {
  server: string
  username?: string
  password?: string
}

export interface Account {
  id: string
  label: string
  partition: string
  proxy: Proxy | null
  userAgent: string | null
  notes: string
  dailyGoalMinutes: number
  createdAt: string
}

export interface AccountsFile {
  version: 1
  accounts: Account[]
}

export interface StatsFile {
  version: 1
  days: Record<string, Record<string, number>>
}

export interface Rect {
  x: number
  y: number
  width: number
  height: number
}

export interface CellRect extends Rect {
  id: string
}

export type ViewStatus = 'stopped' | 'loading' | 'ready' | 'error'
```

- [ ] **Step 5: Câbler les scripts npm**

`pnpm init` écrit `"type": "module"` dans `package.json`. **Cette ligne doit
rester supprimée** (Task 1 l'a retirée) : le main et le preload sont compilés en
CommonJS, et `"type": "module"` ferait échouer leur chargement au démarrage.

Dans `package.json`, remplacer le bloc `"scripts"` par :

```json
  "main": "dist/main/index.js",
  "scripts": {
    "build": "tsc -p tsconfig.json && tsc -p tsconfig.renderer.json",
    "start": "pnpm build && electron .",
    "test": "vitest run",
    "test:watch": "vitest"
  },
```

- [ ] **Step 6: Vérifier que la chaîne tourne**

```bash
pnpm build && pnpm test
```

Attendu : la compilation passe ; Vitest signale « No test files found » et sort en succès (aucun test n'existe encore).

- [ ] **Step 7: Committer**

```bash
git add tsconfig.json tsconfig.renderer.json vitest.config.ts src/core/types.ts package.json
git commit -m "chore: add typescript, vitest and shared types"
```

---

### Task 3: Géométrie de la grille

Fonction pure : à partir de la liste des comptes d'une page, de la cellule focalisée et de la zone disponible, elle produit le rectangle de chaque vue. C'est le cœur du positionnement natif, donc la partie qui doit être la plus solidement testée.

**Files:**
- Create: `src/core/layout.ts`
- Test: `tests/layout.test.ts`

**Interfaces:**
- Consumes: `Rect`, `CellRect` (Task 2)
- Produces: `computeLayout(input: LayoutInput): CellRect[]` et `columnsFor(count: number): number`. La Task 8 applique ces rectangles ; la Task 10 dessine le châssis aux mêmes coordonnées.

- [ ] **Step 1: Écrire les tests qui échouent**

`tests/layout.test.ts` :

```typescript
import { describe, it, expect } from 'vitest'
import { computeLayout, columnsFor } from '../src/core/layout'

const viewport = { x: 0, y: 0, width: 1200, height: 800 }
const base = { viewport, gap: 10, cellHeaderHeight: 30 }

describe('columnsFor', () => {
  it('utilise une colonne pour un seul compte', () => {
    expect(columnsFor(1)).toBe(1)
  })

  it('utilise deux colonnes jusqu a quatre comptes', () => {
    expect(columnsFor(2)).toBe(2)
    expect(columnsFor(4)).toBe(2)
  })

  it('utilise trois colonnes au dela de quatre comptes', () => {
    expect(columnsFor(5)).toBe(3)
    expect(columnsFor(6)).toBe(3)
  })
})

describe('computeLayout sans focus', () => {
  it('ne renvoie rien pour une page vide', () => {
    expect(computeLayout({ ...base, ids: [], focusedId: null })).toEqual([])
  })

  it('donne toute la zone a un compte unique, moins son en-tete', () => {
    const [cell] = computeLayout({ ...base, ids: ['a'], focusedId: null })
    expect(cell).toEqual({ id: 'a', x: 0, y: 30, width: 1200, height: 770 })
  })

  it('repartit quatre comptes en deux colonnes egales', () => {
    const cells = computeLayout({ ...base, ids: ['a', 'b', 'c', 'd'], focusedId: null })
    expect(cells).toHaveLength(4)
    // largeur = (1200 - 1 gap) / 2 = 595 ; hauteur = (800 - 1 gap) / 2 = 395
    expect(cells[0]).toEqual({ id: 'a', x: 0, y: 30, width: 595, height: 365 })
    expect(cells[1]).toEqual({ id: 'b', x: 605, y: 30, width: 595, height: 365 })
    expect(cells[2]).toEqual({ id: 'c', x: 0, y: 435, width: 595, height: 365 })
    expect(cells[3]).toEqual({ id: 'd', x: 605, y: 435, width: 595, height: 365 })
  })

  it('ne laisse aucune cellule deborder de la zone', () => {
    const cells = computeLayout({ ...base, ids: ['a', 'b', 'c', 'd', 'e', 'f'], focusedId: null })
    for (const cell of cells) {
      expect(cell.x).toBeGreaterThanOrEqual(viewport.x)
      expect(cell.y).toBeGreaterThanOrEqual(viewport.y)
      expect(cell.x + cell.width).toBeLessThanOrEqual(viewport.x + viewport.width)
      expect(cell.y + cell.height).toBeLessThanOrEqual(viewport.y + viewport.height)
    }
  })
})

describe('computeLayout avec focus', () => {
  it('donne les deux tiers gauche a la cellule focalisee', () => {
    const cells = computeLayout({ ...base, ids: ['a', 'b', 'c'], focusedId: 'a' })
    const focused = cells.find(c => c.id === 'a')!
    expect(focused.x).toBe(0)
    expect(focused.y).toBe(30)
    expect(focused.width).toBe(790) // round(1200 * 2/3) - gap = 800 - 10
    expect(focused.height).toBe(770)
  })

  it('empile les cellules non focalisees dans la colonne de droite', () => {
    const cells = computeLayout({ ...base, ids: ['a', 'b', 'c'], focusedId: 'a' })
    const others = cells.filter(c => c.id !== 'a')
    expect(others).toHaveLength(2)
    for (const cell of others) {
      expect(cell.x).toBe(800)
      expect(cell.width).toBe(400)
    }
    expect(others[0].y).toBe(30)   // 0 + en-tete
    expect(others[1].y).toBe(435)  // 395 + gap + en-tete
  })

  it('se comporte comme sans focus si l id focalise est absent de la page', () => {
    const withGhost = computeLayout({ ...base, ids: ['a', 'b'], focusedId: 'zzz' })
    const without = computeLayout({ ...base, ids: ['a', 'b'], focusedId: null })
    expect(withGhost).toEqual(without)
  })

  it('donne toute la zone a une cellule focalisee seule sur sa page', () => {
    const cells = computeLayout({ ...base, ids: ['a'], focusedId: 'a' })
    expect(cells[0]).toEqual({ id: 'a', x: 0, y: 30, width: 1200, height: 770 })
  })
})
```

- [ ] **Step 2: Lancer les tests pour vérifier qu'ils échouent**

Run: `pnpm exec vitest run tests/layout.test.ts`
Expected: FAIL — `Failed to resolve import "../src/core/layout"`.

- [ ] **Step 3: Implémenter**

`src/core/layout.ts` :

```typescript
import type { Rect, CellRect } from './types'

export interface LayoutInput {
  /** Comptes de la page courante, dans l'ordre d'affichage. */
  ids: string[]
  /** Compte focalise, ou null. Ignore s'il n'est pas dans `ids`. */
  focusedId: string | null
  /** Zone disponible pour les cellules, en-tete d'application deja deduit. */
  viewport: Rect
  /** Espacement entre cellules, en pixels. */
  gap: number
  /** Bandeau dessine par le chassis au-dessus de chaque vue. */
  cellHeaderHeight: number
}

export function columnsFor (count: number): number {
  if (count <= 1) return 1
  if (count <= 4) return 2
  return 3
}

/**
 * Les rectangles renvoyes sont ceux des *vues*, pas des cellules : le bandeau
 * d'en-tete est deja retranche du haut. Le chassis dessine ce bandeau dans
 * l'espace ainsi libere.
 */
export function computeLayout (input: LayoutInput): CellRect[] {
  const { ids, viewport, gap, cellHeaderHeight } = input
  if (ids.length === 0) return []

  const focusedId = ids.includes(input.focusedId ?? '') ? input.focusedId : null

  if (focusedId === null || ids.length === 1) {
    return uniformGrid(ids, viewport, gap, cellHeaderHeight)
  }
  return focusedGrid(ids, focusedId, viewport, gap, cellHeaderHeight)
}

function uniformGrid (
  ids: string[], viewport: Rect, gap: number, headerHeight: number
): CellRect[] {
  const cols = columnsFor(ids.length)
  const rows = Math.ceil(ids.length / cols)
  const cellWidth = Math.floor((viewport.width - gap * (cols - 1)) / cols)
  const cellHeight = Math.floor((viewport.height - gap * (rows - 1)) / rows)

  return ids.map((id, index) => {
    const col = index % cols
    const row = Math.floor(index / cols)
    return {
      id,
      x: viewport.x + col * (cellWidth + gap),
      y: viewport.y + row * (cellHeight + gap) + headerHeight,
      width: cellWidth,
      height: cellHeight - headerHeight
    }
  })
}

function focusedGrid (
  ids: string[], focusedId: string, viewport: Rect, gap: number, headerHeight: number
): CellRect[] {
  const railWidth = Math.round(viewport.width / 3)
  const mainWidth = viewport.width - railWidth - gap
  const others = ids.filter(id => id !== focusedId)
  const railCellHeight = Math.floor((viewport.height - gap * (others.length - 1)) / others.length)

  const focused: CellRect = {
    id: focusedId,
    x: viewport.x,
    y: viewport.y + headerHeight,
    width: mainWidth,
    height: viewport.height - headerHeight
  }

  const rail: CellRect[] = others.map((id, index) => ({
    id,
    x: viewport.x + mainWidth + gap,
    y: viewport.y + index * (railCellHeight + gap) + headerHeight,
    width: railWidth,
    height: railCellHeight - headerHeight
  }))

  // L'ordre suit `ids` pour que le chassis et les vues restent alignes.
  return ids.map(id => (id === focusedId ? focused : rail.find(c => c.id === id)!))
}
```

- [ ] **Step 4: Lancer les tests pour vérifier qu'ils passent**

Run: `pnpm exec vitest run tests/layout.test.ts`
Expected: PASS — 11 tests.

- [ ] **Step 5: Committer**

```bash
git add src/core/layout.ts tests/layout.test.ts
git commit -m "feat: add grid geometry computation"
```

> **Amendement post-revue (commit `dc19773`).** Le code livré ajoute deux
> protections absentes du bloc ci-dessus, et fait foi : les `width`/`height`
> renvoyés sont bornés à 0 (une fenêtre rétrécie ne doit jamais transmettre de
> dimension négative à `setBounds()`), et `computeLayout` lève `ids en double`
> si `ids` contient un doublon. Les bornes ne s'appliquent qu'aux dimensions,
> jamais aux coordonnées. 16 tests.

---

### Task 4: Agrégation du temps passé

**Files:**
- Create: `src/core/stats.ts`
- Test: `tests/stats.test.ts`

**Interfaces:**
- Consumes: `StatsFile` (Task 2)
- Produces: `emptyStats()`, `addSeconds(stats, day, accountId, seconds)`, `secondsFor(stats, day, accountId)`, `purgeOlderThan(stats, cutoffDay)`, `dayKey(date: Date): string`. La Task 11 les appelle à chaque tick.

Toutes ces fonctions sont pures et immuables, et la date leur est **passée en paramètre** — aucune ne lit l'horloge. C'est ce qui les rend testables sans geler le temps.

- [ ] **Step 1: Écrire les tests qui échouent**

`tests/stats.test.ts` :

```typescript
import { describe, it, expect } from 'vitest'
import { emptyStats, addSeconds, secondsFor, purgeOlderThan, dayKey } from '../src/core/stats'

describe('dayKey', () => {
  it('formate une date en AAAA-MM-JJ local', () => {
    expect(dayKey(new Date(2026, 7, 6, 14, 30))).toBe('2026-08-06')
  })

  it('complete les mois et jours a un chiffre', () => {
    expect(dayKey(new Date(2026, 0, 3, 9, 0))).toBe('2026-01-03')
  })
})

describe('addSeconds', () => {
  it('cree le jour et le compte au premier ajout', () => {
    const next = addSeconds(emptyStats(), '2026-08-06', 'a1', 5)
    expect(secondsFor(next, '2026-08-06', 'a1')).toBe(5)
  })

  it('cumule les ajouts successifs', () => {
    let stats = emptyStats()
    stats = addSeconds(stats, '2026-08-06', 'a1', 5)
    stats = addSeconds(stats, '2026-08-06', 'a1', 7)
    expect(secondsFor(stats, '2026-08-06', 'a1')).toBe(12)
  })

  it('garde les comptes independants', () => {
    let stats = emptyStats()
    stats = addSeconds(stats, '2026-08-06', 'a1', 5)
    stats = addSeconds(stats, '2026-08-06', 'b2', 9)
    expect(secondsFor(stats, '2026-08-06', 'a1')).toBe(5)
    expect(secondsFor(stats, '2026-08-06', 'b2')).toBe(9)
  })

  it('garde les jours independants', () => {
    let stats = emptyStats()
    stats = addSeconds(stats, '2026-08-06', 'a1', 5)
    stats = addSeconds(stats, '2026-08-07', 'a1', 3)
    expect(secondsFor(stats, '2026-08-06', 'a1')).toBe(5)
    expect(secondsFor(stats, '2026-08-07', 'a1')).toBe(3)
  })

  it('ne modifie pas l objet source', () => {
    const original = emptyStats()
    addSeconds(original, '2026-08-06', 'a1', 5)
    expect(original.days).toEqual({})
  })
})

describe('secondsFor', () => {
  it('renvoie zero pour un jour inconnu', () => {
    expect(secondsFor(emptyStats(), '2026-08-06', 'a1')).toBe(0)
  })

  it('renvoie zero pour un compte inconnu dans un jour connu', () => {
    const stats = addSeconds(emptyStats(), '2026-08-06', 'a1', 5)
    expect(secondsFor(stats, '2026-08-06', 'inconnu')).toBe(0)
  })
})

describe('purgeOlderThan', () => {
  it('supprime les jours strictement anterieurs au seuil', () => {
    let stats = emptyStats()
    stats = addSeconds(stats, '2026-05-01', 'a1', 5)
    stats = addSeconds(stats, '2026-08-06', 'a1', 5)
    const purged = purgeOlderThan(stats, '2026-08-01')
    expect(Object.keys(purged.days)).toEqual(['2026-08-06'])
  })

  it('conserve le jour seuil lui-meme', () => {
    const stats = addSeconds(emptyStats(), '2026-08-01', 'a1', 5)
    expect(Object.keys(purgeOlderThan(stats, '2026-08-01').days)).toEqual(['2026-08-01'])
  })
})
```

- [ ] **Step 2: Lancer les tests pour vérifier qu'ils échouent**

Run: `pnpm exec vitest run tests/stats.test.ts`
Expected: FAIL — `Failed to resolve import "../src/core/stats"`.

- [ ] **Step 3: Implémenter**

`src/core/stats.ts` :

```typescript
import type { StatsFile } from './types'

export function emptyStats (): StatsFile {
  return { version: 1, days: {} }
}

/** Cle de jour locale au format AAAA-MM-JJ. */
export function dayKey (date: Date): string {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

export function addSeconds (
  stats: StatsFile, day: string, accountId: string, seconds: number
): StatsFile {
  const dayEntry = stats.days[day] ?? {}
  return {
    ...stats,
    days: {
      ...stats.days,
      [day]: { ...dayEntry, [accountId]: (dayEntry[accountId] ?? 0) + seconds }
    }
  }
}

export function secondsFor (stats: StatsFile, day: string, accountId: string): number {
  return stats.days[day]?.[accountId] ?? 0
}

/** Supprime les jours strictement anterieurs a `cutoffDay`. Les cles AAAA-MM-JJ se comparent lexicographiquement. */
export function purgeOlderThan (stats: StatsFile, cutoffDay: string): StatsFile {
  const days: StatsFile['days'] = {}
  for (const [day, entry] of Object.entries(stats.days)) {
    if (day >= cutoffDay) days[day] = entry
  }
  return { ...stats, days }
}
```

- [ ] **Step 4: Lancer les tests pour vérifier qu'ils passent**

Run: `pnpm exec vitest run tests/stats.test.ts`
Expected: PASS — 11 tests.

- [ ] **Step 5: Committer**

```bash
git add src/core/stats.ts tests/stats.test.ts
git commit -m "feat: add time tracking aggregation"
```

---

### Task 5: CRUD des comptes et migration de schéma

**Files:**
- Create: `src/core/accounts.ts`
- Test: `tests/accounts.test.ts`

**Interfaces:**
- Consumes: `Account`, `AccountsFile`, `PAGE_SIZE` (Task 2)
- Produces: `emptyAccounts()`, `createAccount(file, input)`, `updateAccount(file, id, patch)`, `deleteAccount(file, id)`, `migrate(raw)`, `partitionFor(id)`, `pageOf(accounts, pageIndex)`. La Task 9 les expose par IPC ; la Task 13 utilise `pageOf`.

`id` et `createdAt` sont **injectés** par l'appelant plutôt que générés dans le module, pour que les tests soient déterministes.

- [ ] **Step 1: Écrire les tests qui échouent**

`tests/accounts.test.ts` :

```typescript
import { describe, it, expect } from 'vitest'
import {
  emptyAccounts, createAccount, updateAccount, deleteAccount,
  migrate, partitionFor, pageOf
} from '../src/core/accounts'

const input = { id: 'a1', label: '@niche', createdAt: '2026-08-06T12:00:00Z' }

describe('partitionFor', () => {
  it('prefixe l identifiant pour obtenir une partition persistante', () => {
    expect(partitionFor('a1')).toBe('persist:tt-a1')
  })
})

describe('createAccount', () => {
  it('ajoute un compte avec ses valeurs par defaut', () => {
    const file = createAccount(emptyAccounts(), input)
    expect(file.accounts).toHaveLength(1)
    expect(file.accounts[0]).toEqual({
      id: 'a1',
      label: '@niche',
      partition: 'persist:tt-a1',
      proxy: null,
      userAgent: null,
      notes: '',
      dailyGoalMinutes: 15,
      createdAt: '2026-08-06T12:00:00Z'
    })
  })

  it('ajoute a la fin de la liste', () => {
    let file = createAccount(emptyAccounts(), input)
    file = createAccount(file, { ...input, id: 'b2', label: '@autre' })
    expect(file.accounts.map(a => a.id)).toEqual(['a1', 'b2'])
  })

  it('refuse un identifiant deja utilise', () => {
    const file = createAccount(emptyAccounts(), input)
    expect(() => createAccount(file, input)).toThrow('identifiant deja utilise')
  })

  it('ne modifie pas l objet source', () => {
    const original = emptyAccounts()
    createAccount(original, input)
    expect(original.accounts).toEqual([])
  })
})

describe('updateAccount', () => {
  it('applique un patch partiel', () => {
    const file = updateAccount(createAccount(emptyAccounts(), input), 'a1', { notes: 'cuisine' })
    expect(file.accounts[0].notes).toBe('cuisine')
    expect(file.accounts[0].label).toBe('@niche')
  })

  it('accepte un proxy', () => {
    const file = updateAccount(createAccount(emptyAccounts(), input), 'a1', {
      proxy: { server: 'http://proxy.example:8080' }
    })
    expect(file.accounts[0].proxy).toEqual({ server: 'http://proxy.example:8080' })
  })

  it('refuse de changer l identifiant ou la partition', () => {
    const file = createAccount(emptyAccounts(), input)
    // @ts-expect-error on verifie la protection a l execution
    expect(() => updateAccount(file, 'a1', { id: 'autre' })).toThrow('champ immuable')
    // @ts-expect-error on verifie la protection a l execution
    expect(() => updateAccount(file, 'a1', { partition: 'persist:x' })).toThrow('champ immuable')
  })

  it('leve une erreur si le compte n existe pas', () => {
    expect(() => updateAccount(emptyAccounts(), 'inconnu', { notes: 'x' })).toThrow('compte introuvable')
  })
})

describe('deleteAccount', () => {
  it('retire le compte demande', () => {
    let file = createAccount(emptyAccounts(), input)
    file = createAccount(file, { ...input, id: 'b2', label: '@autre' })
    expect(deleteAccount(file, 'a1').accounts.map(a => a.id)).toEqual(['b2'])
  })

  it('leve une erreur si le compte n existe pas', () => {
    expect(() => deleteAccount(emptyAccounts(), 'inconnu')).toThrow('compte introuvable')
  })
})

describe('migrate', () => {
  it('renvoie un fichier vide pour une entree nulle ou invalide', () => {
    expect(migrate(null)).toEqual(emptyAccounts())
    expect(migrate('nawak')).toEqual(emptyAccounts())
    expect(migrate({ version: 99 })).toEqual(emptyAccounts())
  })

  it('conserve un fichier valide', () => {
    const file = createAccount(emptyAccounts(), input)
    expect(migrate(file)).toEqual(file)
  })

  it('complete les champs manquants d un compte partiel', () => {
    const raw = { version: 1, accounts: [{ id: 'a1', label: '@niche' }] }
    const account = migrate(raw).accounts[0]
    expect(account.partition).toBe('persist:tt-a1')
    expect(account.proxy).toBeNull()
    expect(account.notes).toBe('')
    expect(account.dailyGoalMinutes).toBe(15)
  })

  it('ecarte les entrees sans identifiant', () => {
    const raw = { version: 1, accounts: [{ label: 'sans id' }, { id: 'a1', label: 'ok' }] }
    expect(migrate(raw).accounts.map(a => a.id)).toEqual(['a1'])
  })
})

describe('pageOf', () => {
  const many = Array.from({ length: 8 }, (_, i) => ({ ...input, id: `id${i}` }))
    .reduce((file, a) => createAccount(file, a), emptyAccounts()).accounts

  it('renvoie les six premiers comptes en page zero', () => {
    expect(pageOf(many, 0).map(a => a.id)).toEqual(['id0', 'id1', 'id2', 'id3', 'id4', 'id5'])
  })

  it('renvoie le reste en page un', () => {
    expect(pageOf(many, 1).map(a => a.id)).toEqual(['id6', 'id7'])
  })

  it('renvoie une liste vide au-dela de la derniere page', () => {
    expect(pageOf(many, 5)).toEqual([])
  })
})
```

- [ ] **Step 2: Lancer les tests pour vérifier qu'ils échouent**

Run: `pnpm exec vitest run tests/accounts.test.ts`
Expected: FAIL — `Failed to resolve import "../src/core/accounts"`.

- [ ] **Step 3: Implémenter**

`src/core/accounts.ts` :

```typescript
import { PAGE_SIZE } from './types'
import type { Account, AccountsFile } from './types'

export const DEFAULT_GOAL_MINUTES = 15

export interface CreateAccountInput {
  id: string
  label: string
  createdAt: string
}

/** Champs qu'un patch ne peut pas toucher : ils identifient le stockage du compte. */
export type AccountPatch = Partial<Omit<Account, 'id' | 'partition' | 'createdAt'>>

export function partitionFor (id: string): string {
  return `persist:tt-${id}`
}

export function emptyAccounts (): AccountsFile {
  return { version: 1, accounts: [] }
}

export function createAccount (file: AccountsFile, input: CreateAccountInput): AccountsFile {
  if (file.accounts.some(a => a.id === input.id)) {
    throw new Error(`identifiant deja utilise : ${input.id}`)
  }
  const account: Account = {
    id: input.id,
    label: input.label,
    partition: partitionFor(input.id),
    proxy: null,
    userAgent: null,
    notes: '',
    dailyGoalMinutes: DEFAULT_GOAL_MINUTES,
    createdAt: input.createdAt
  }
  return { ...file, accounts: [...file.accounts, account] }
}

export function updateAccount (
  file: AccountsFile, id: string, patch: AccountPatch
): AccountsFile {
  for (const key of ['id', 'partition', 'createdAt']) {
    if (key in patch) throw new Error(`champ immuable : ${key}`)
  }
  if (!file.accounts.some(a => a.id === id)) {
    throw new Error(`compte introuvable : ${id}`)
  }
  return {
    ...file,
    accounts: file.accounts.map(a => (a.id === id ? { ...a, ...patch } : a))
  }
}

export function deleteAccount (file: AccountsFile, id: string): AccountsFile {
  if (!file.accounts.some(a => a.id === id)) {
    throw new Error(`compte introuvable : ${id}`)
  }
  return { ...file, accounts: file.accounts.filter(a => a.id !== id) }
}

/**
 * Normalise un contenu de fichier lu sur disque. Tout ce qui n'est pas
 * reconnaissable retombe sur un fichier vide plutot que de faire planter
 * le demarrage.
 */
export function migrate (raw: unknown): AccountsFile {
  if (typeof raw !== 'object' || raw === null) return emptyAccounts()
  const candidate = raw as Partial<AccountsFile>
  if (candidate.version !== 1 || !Array.isArray(candidate.accounts)) return emptyAccounts()

  const accounts: Account[] = []
  for (const entry of candidate.accounts) {
    if (typeof entry !== 'object' || entry === null) continue
    const partial = entry as Partial<Account>
    if (typeof partial.id !== 'string' || partial.id === '') continue
    accounts.push({
      id: partial.id,
      label: typeof partial.label === 'string' ? partial.label : partial.id,
      partition: partitionFor(partial.id),
      proxy: partial.proxy ?? null,
      userAgent: partial.userAgent ?? null,
      notes: typeof partial.notes === 'string' ? partial.notes : '',
      dailyGoalMinutes: typeof partial.dailyGoalMinutes === 'number'
        ? partial.dailyGoalMinutes
        : DEFAULT_GOAL_MINUTES,
      createdAt: typeof partial.createdAt === 'string'
        ? partial.createdAt
        : new Date(0).toISOString()
    })
  }
  return { version: 1, accounts }
}

export function pageOf (accounts: Account[], pageIndex: number): Account[] {
  const start = pageIndex * PAGE_SIZE
  return accounts.slice(start, start + PAGE_SIZE)
}
```

- [ ] **Step 4: Lancer les tests pour vérifier qu'ils passent**

Run: `pnpm exec vitest run tests/accounts.test.ts`
Expected: PASS — 17 tests.

- [ ] **Step 5: Committer**

```bash
git add src/core/accounts.ts tests/accounts.test.ts
git commit -m "feat: add account CRUD and schema migration"
```

---

### Task 6: Stockage atomique sur disque

**Files:**
- Create: `src/main/storage.ts`
- Test: `tests/storage.test.ts`

**Interfaces:**
- Consumes: rien
- Produces: `readJson<T>(path, fallback): Promise<T>`, `writeJsonAtomic(path, data): Promise<void>`. Les Tasks 9 et 11 les utilisent.

Ce module vit dans `src/main/` car il touche au système de fichiers, mais il n'importe pas `electron` — les chemins lui sont passés en paramètre, ce qui permet de le tester dans un dossier temporaire.

- [ ] **Step 1: Écrire les tests qui échouent**

`tests/storage.test.ts` :

```typescript
import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { mkdtemp, rm, writeFile, readdir } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { readJson, writeJsonAtomic } from '../src/main/storage'

let dir: string

beforeEach(async () => {
  dir = await mkdtemp(join(tmpdir(), 'tcc-'))
})

afterEach(async () => {
  await rm(dir, { recursive: true, force: true })
})

describe('readJson', () => {
  it('renvoie la valeur de repli si le fichier n existe pas', async () => {
    const result = await readJson(join(dir, 'absent.json'), { version: 1 })
    expect(result).toEqual({ version: 1 })
  })

  it('renvoie la valeur de repli si le fichier est corrompu', async () => {
    const path = join(dir, 'casse.json')
    await writeFile(path, '{ ceci n est pas du json')
    expect(await readJson(path, { version: 1 })).toEqual({ version: 1 })
  })

  it('relit ce qui a ete ecrit', async () => {
    const path = join(dir, 'ok.json')
    await writeJsonAtomic(path, { version: 1, accounts: ['a'] })
    expect(await readJson(path, null)).toEqual({ version: 1, accounts: ['a'] })
  })
})

describe('writeJsonAtomic', () => {
  it('cree les dossiers parents manquants', async () => {
    const path = join(dir, 'imbrique', 'profond', 'data.json')
    await writeJsonAtomic(path, { ok: true })
    expect(await readJson(path, null)).toEqual({ ok: true })
  })

  it('ne laisse aucun fichier temporaire derriere lui', async () => {
    await writeJsonAtomic(join(dir, 'data.json'), { ok: true })
    expect(await readdir(dir)).toEqual(['data.json'])
  })

  it('remplace le contenu precedent', async () => {
    const path = join(dir, 'data.json')
    await writeJsonAtomic(path, { valeur: 1 })
    await writeJsonAtomic(path, { valeur: 2 })
    expect(await readJson(path, null)).toEqual({ valeur: 2 })
  })
})
```

- [ ] **Step 2: Lancer les tests pour vérifier qu'ils échouent**

Run: `pnpm exec vitest run tests/storage.test.ts`
Expected: FAIL — `Failed to resolve import "../src/main/storage"`.

- [ ] **Step 3: Implémenter**

`src/main/storage.ts` :

```typescript
import { readFile, writeFile, rename, mkdir, unlink } from 'node:fs/promises'
import { dirname, join, basename } from 'node:path'

/** Lit un JSON. Un fichier absent ou illisible retombe sur `fallback` plutot que de lever. */
export async function readJson<T> (path: string, fallback: T): Promise<T> {
  try {
    return JSON.parse(await readFile(path, 'utf8')) as T
  } catch {
    return fallback
  }
}

/**
 * Ecrit un JSON en deux temps : fichier temporaire puis `rename`. Le `rename`
 * etant atomique sur un meme volume, une coupure en cours d'ecriture laisse
 * l'ancien fichier intact au lieu d'un fichier tronque.
 */
export async function writeJsonAtomic (path: string, data: unknown): Promise<void> {
  const dir = dirname(path)
  await mkdir(dir, { recursive: true })
  const tmp = join(dir, `.${basename(path)}.${process.pid}.tmp`)
  try {
    await writeFile(tmp, JSON.stringify(data, null, 2), 'utf8')
    await rename(tmp, path)
  } catch (error) {
    await unlink(tmp).catch(() => {})
    throw error
  }
}
```

- [ ] **Step 4: Lancer les tests pour vérifier qu'ils passent**

Run: `pnpm exec vitest run tests/storage.test.ts`
Expected: PASS — 6 tests.

- [ ] **Step 5: Committer**

```bash
git add src/main/storage.ts tests/storage.test.ts
git commit -m "feat: add atomic json storage"
```

---

### Task 7: Sessions — user-agent et proxy par compte

**Files:**
- Create: `src/core/user-agent.ts`
- Create: `src/main/session-manager.ts`
- Test: `tests/user-agent.test.ts`

**Interfaces:**
- Consumes: `Account` (Task 2), `partitionFor` (Task 5)
- Produces: `stripElectronTokens(ua, appName)` (pur, testé) et `configureSession(account): Session` (Electron, vérifié à la main). La Task 8 appelle `configureSession` avant de créer une vue.

La partie testable — le nettoyage du user-agent — est isolée dans `src/core/`. Le reste est un mince câblage Electron.

- [ ] **Step 1: Écrire les tests qui échouent**

`tests/user-agent.test.ts` :

```typescript
import { describe, it, expect } from 'vitest'
import { stripElectronTokens } from '../src/core/user-agent'

const ELECTRON_UA =
  'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 ' +
  '(KHTML, like Gecko) tiktok-control-center/0.1.0 Chrome/142.0.0.0 ' +
  'Electron/43.3.0 Safari/537.36'

describe('stripElectronTokens', () => {
  it('retire le jeton Electron et le jeton de l application', () => {
    expect(stripElectronTokens(ELECTRON_UA, 'tiktok-control-center')).toBe(
      'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 ' +
      '(KHTML, like Gecko) Chrome/142.0.0.0 Safari/537.36'
    )
  })

  it('conserve la version de Chrome intacte', () => {
    expect(stripElectronTokens(ELECTRON_UA, 'tiktok-control-center')).toContain('Chrome/142.0.0.0')
  })

  it('ne laisse aucune trace du mot Electron', () => {
    expect(stripElectronTokens(ELECTRON_UA, 'tiktok-control-center')).not.toContain('Electron')
  })

  it('laisse intact un user-agent Chrome deja propre', () => {
    const clean = 'Mozilla/5.0 (Macintosh) AppleWebKit/537.36 Chrome/142.0.0.0 Safari/537.36'
    expect(stripElectronTokens(clean, 'tiktok-control-center')).toBe(clean)
  })

  it('echappe les caracteres speciaux du nom d application', () => {
    const ua = 'Mozilla/5.0 my.app+v2/1.0 Chrome/142.0.0.0 Safari/537.36'
    expect(stripElectronTokens(ua, 'my.app+v2')).toBe(
      'Mozilla/5.0 Chrome/142.0.0.0 Safari/537.36'
    )
  })

  it('ne laisse pas de double espace', () => {
    expect(stripElectronTokens(ELECTRON_UA, 'tiktok-control-center')).not.toContain('  ')
  })
})
```

- [ ] **Step 2: Lancer les tests pour vérifier qu'ils échouent**

Run: `pnpm exec vitest run tests/user-agent.test.ts`
Expected: FAIL — `Failed to resolve import "../src/core/user-agent"`.

- [ ] **Step 3: Implémenter la fonction pure**

`src/core/user-agent.ts` :

```typescript
function escapeRegExp (value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

/**
 * Retire du user-agent les jetons ajoutes par Electron : `Electron/<version>`
 * et `<nom-app>/<version>`. Ce qui reste est le user-agent Chrome authentique
 * du Chromium embarque — donc toujours coherent avec la version reelle du
 * moteur, contrairement a une chaine ecrite en dur qui se perimerait.
 */
export function stripElectronTokens (ua: string, appName: string): string {
  return ua
    .replace(/\s?Electron\/\S+/, '')
    .replace(new RegExp(`\\s?${escapeRegExp(appName)}\\/\\S+`), '')
    .replace(/\s{2,}/g, ' ')
    .trim()
}
```

- [ ] **Step 4: Lancer les tests pour vérifier qu'ils passent**

Run: `pnpm exec vitest run tests/user-agent.test.ts`
Expected: PASS — 6 tests.

- [ ] **Step 5: Implémenter le gestionnaire de sessions**

`src/main/session-manager.ts` :

```typescript
import { app, session } from 'electron'
import type { Session } from 'electron'
import { stripElectronTokens } from '../core/user-agent'
import type { Account } from '../core/types'

/**
 * Prepare la session d'un compte : user-agent credible et proxy si configure.
 * Idempotent — appeler plusieurs fois pour le meme compte est sans effet de bord.
 */
export async function configureSession (account: Account): Promise<Session> {
  const ses = session.fromPartition(account.partition)

  const ua = account.userAgent ?? stripElectronTokens(ses.getUserAgent(), app.getName())
  ses.setUserAgent(ua)

  if (account.proxy) {
    await ses.setProxy({ proxyRules: account.proxy.server })
  } else {
    await ses.setProxy({ mode: 'direct' })
  }

  return ses
}

/**
 * Repond aux demandes d'authentification proxy. A brancher une seule fois au
 * demarrage. Sans cela, un proxy authentifie fait echouer tous les chargements
 * en silence.
 */
export function installProxyAuthHandler (lookup: (partition: string) => Account | undefined): void {
  app.on('login', (event, webContents, _details, authInfo, callback) => {
    if (!authInfo.isProxy) return
    const partition = webContents?.session.storagePath ?? ''
    const account = lookup(partition)
    if (!account?.proxy?.username) return
    event.preventDefault()
    callback(account.proxy.username, account.proxy.password ?? '')
  })
}

/** Efface toutes les donnees d'un compte supprime. */
export async function destroySession (account: Account): Promise<void> {
  await session.fromPartition(account.partition).clearStorageData()
}
```

- [ ] **Step 6: Vérifier la compilation**

Run: `pnpm exec tsc -p tsconfig.json --noEmit`
Expected: aucune erreur.

- [ ] **Step 7: Committer**

```bash
git add src/core/user-agent.ts src/main/session-manager.ts tests/user-agent.test.ts
git commit -m "feat: add per-account session config with clean user agent"
```

---

### Task 8: Gestionnaire de vues

**Files:**
- Create: `src/main/view-manager.ts`

**Interfaces:**
- Consumes: `configureSession`, `destroySession` (Task 7), `CellRect`, `ViewStatus`, `Account` (Task 2)
- Produces: la classe `ViewManager` avec `attach(window)`, `start(account)`, `stop(id)`, `reload(id)`, `destroy(account)`, `applyLayout(cells, focusedId)`, `onStatus(listener)`. La Task 9 l'appelle depuis l'IPC.

- [ ] **Step 1: Implémenter**

`src/main/view-manager.ts` :

```typescript
import { WebContentsView } from 'electron'
import type { BaseWindow } from 'electron'
import { configureSession, destroySession } from './session-manager'
import type { Account, CellRect, ViewStatus } from '../core/types'

const HIDDEN: CellRect = { id: '', x: 0, y: 0, width: 0, height: 0 }

export interface StatusEvent {
  id: string
  status: ViewStatus
  url: string
  title: string
  errorCode?: number
  errorDescription?: string
}

type StatusListener = (event: StatusEvent) => void

export class ViewManager {
  private window: BaseWindow | null = null
  private readonly views = new Map<string, WebContentsView>()
  private readonly statuses = new Map<string, ViewStatus>()
  private listener: StatusListener = () => {}

  attach (window: BaseWindow): void {
    this.window = window
  }

  onStatus (listener: StatusListener): void {
    this.listener = listener
  }

  has (id: string): boolean {
    return this.views.has(id)
  }

  statusOf (id: string): ViewStatus {
    return this.statuses.get(id) ?? 'stopped'
  }

  async start (account: Account): Promise<void> {
    if (this.window === null) throw new Error('ViewManager non attache a une fenetre')
    if (this.views.has(account.id)) return

    await configureSession(account)

    const view = new WebContentsView({
      webPreferences: {
        partition: account.partition,
        contextIsolation: true,
        nodeIntegration: false
      }
    })

    this.wireStatusEvents(account.id, view)
    this.views.set(account.id, view)
    // Hors ecran jusqu'au premier applyLayout, pour eviter un flash en haut a gauche.
    view.setBounds(HIDDEN)
    this.window.contentView.addChildView(view)
    await view.webContents.loadURL('https://www.tiktok.com/')
  }

  stop (id: string): void {
    const view = this.views.get(id)
    if (view === undefined || this.window === null) return
    this.window.contentView.removeChildView(view)
    view.webContents.close()
    this.views.delete(id)
    this.setStatus(id, 'stopped', '', '')
  }

  reload (id: string): void {
    this.views.get(id)?.webContents.reload()
  }

  async destroy (account: Account): Promise<void> {
    this.stop(account.id)
    this.statuses.delete(account.id)
    await destroySession(account)
  }

  stopAll (): void {
    for (const id of [...this.views.keys()]) this.stop(id)
  }

  /**
   * Positionne chaque vue. Les vues absentes de `cells` — page differente ou
   * compte arrete — sont repliees hors champ plutot que detruites, ce qui
   * preserve leur position dans le fil.
   */
  applyLayout (cells: CellRect[], focusedId: string | null): void {
    const placed = new Set<string>()

    for (const cell of cells) {
      const view = this.views.get(cell.id)
      if (view === undefined) continue
      view.setBounds({ x: cell.x, y: cell.y, width: cell.width, height: cell.height })
      placed.add(cell.id)
      void this.setPlayback(view, cell.id === focusedId)
    }

    for (const [id, view] of this.views) {
      if (placed.has(id)) continue
      view.setBounds(HIDDEN)
      void this.setPlayback(view, false)
    }
  }

  /**
   * Coupe le son et met en pause les videos des vues non focalisees : plusieurs
   * lecteurs simultanes saturent le processeur. C'est un controle de lecture
   * media local — aucune action n'est envoyee au compte TikTok.
   */
  private async setPlayback (view: WebContentsView, active: boolean): Promise<void> {
    view.webContents.setAudioMuted(!active)
    if (active) return
    try {
      await view.webContents.executeJavaScript(
        'document.querySelectorAll("video").forEach(v => v.pause()); undefined'
      )
    } catch {
      // La page peut etre en cours de navigation : sans importance, le prochain
      // applyLayout repassera.
    }
  }

  private wireStatusEvents (id: string, view: WebContentsView): void {
    const { webContents } = view
    webContents.on('did-start-loading', () => this.setStatus(id, 'loading', webContents.getURL(), ''))
    webContents.on('did-finish-load', () =>
      this.setStatus(id, 'ready', webContents.getURL(), webContents.getTitle()))
    webContents.on('did-fail-load', (_event, errorCode, errorDescription, validatedURL, isMainFrame) => {
      // Les echecs de sous-ressources sont courants sur TikTok et ne doivent pas
      // faire passer la cellule en erreur.
      if (!isMainFrame) return
      if (errorCode === -3) return // ERR_ABORTED : navigation remplacee
      this.listener({ id, status: 'error', url: validatedURL, title: '', errorCode, errorDescription })
      this.statuses.set(id, 'error')
    })
  }

  private setStatus (id: string, status: ViewStatus, url: string, title: string): void {
    this.statuses.set(id, status)
    this.listener({ id, status, url, title })
  }
}
```

- [ ] **Step 2: Vérifier la compilation**

Run: `pnpm exec tsc -p tsconfig.json --noEmit`
Expected: aucune erreur.

- [ ] **Step 3: Committer**

```bash
git add src/main/view-manager.ts
git commit -m "feat: add view manager for account WebContentsViews"
```

---

### Task 9: Bootstrap du main, preload et IPC

C'est la tâche qui rend l'application lançable pour la première fois.

**Files:**
- Create: `src/main/index.ts`
- Create: `src/main/ipc.ts`
- Create: `src/preload/index.ts`

**Interfaces:**
- Consumes: `ViewManager` (Task 8), `readJson`/`writeJsonAtomic` (Task 6), le CRUD des comptes (Task 5), `computeLayout` (Task 3), les stats (Task 4)
- Produces: `window.api` dans le renderer, avec les méthodes listées ci-dessous. La Task 10 les consomme.

Le châssis est lui-même une `WebContentsView` : `BaseWindow` n'a pas de page hôte. Elle est ajoutée en premier et couvre toute la fenêtre ; les vues de comptes se posent par-dessus.

- [ ] **Step 1: Écrire le preload**

`src/preload/index.ts` :

```typescript
import { contextBridge, ipcRenderer } from 'electron'
import type { Account, CellRect } from '../core/types'
import type { StatusEvent } from '../main/view-manager'

export interface Api {
  listAccounts: () => Promise<Account[]>
  createAccount: (label: string) => Promise<Account[]>
  updateAccount: (id: string, patch: Record<string, unknown>) => Promise<Account[]>
  deleteAccount: (id: string) => Promise<Account[]>
  startView: (id: string) => Promise<void>
  stopView: (id: string) => Promise<void>
  reloadView: (id: string) => Promise<void>
  applyLayout: (cells: CellRect[], focusedId: string | null) => Promise<void>
  getStats: () => Promise<Record<string, number>>
  onStatus: (handler: (event: StatusEvent) => void) => void
  onStats: (handler: (seconds: Record<string, number>) => void) => void
}

const api: Api = {
  listAccounts: () => ipcRenderer.invoke('accounts:list'),
  createAccount: (label) => ipcRenderer.invoke('accounts:create', label),
  updateAccount: (id, patch) => ipcRenderer.invoke('accounts:update', id, patch),
  deleteAccount: (id) => ipcRenderer.invoke('accounts:delete', id),
  startView: (id) => ipcRenderer.invoke('view:start', id),
  stopView: (id) => ipcRenderer.invoke('view:stop', id),
  reloadView: (id) => ipcRenderer.invoke('view:reload', id),
  applyLayout: (cells, focusedId) => ipcRenderer.invoke('layout:apply', cells, focusedId),
  getStats: () => ipcRenderer.invoke('stats:today'),
  onStatus: (handler) => { ipcRenderer.on('view:state', (_e, payload) => handler(payload)) },
  onStats: (handler) => { ipcRenderer.on('stats:tick', (_e, payload) => handler(payload)) }
}

contextBridge.exposeInMainWorld('api', api)
```

- [ ] **Step 2: Écrire le registre IPC**

`src/main/ipc.ts` :

```typescript
import { ipcMain, app } from 'electron'
import { randomUUID } from 'node:crypto'
import { join } from 'node:path'
import { readJson, writeJsonAtomic } from './storage'
import { ViewManager } from './view-manager'
import {
  emptyAccounts, createAccount, updateAccount, deleteAccount, migrate
} from '../core/accounts'
import { emptyStats, addSeconds, dayKey, purgeOlderThan } from '../core/stats'
import type { Account, AccountsFile, StatsFile, CellRect } from '../core/types'

const RETENTION_DAYS = 90

export class AppState {
  accounts: AccountsFile = emptyAccounts()
  stats: StatsFile = emptyStats()
  focusedId: string | null = null
  statsDirty = false

  get accountsPath (): string { return join(app.getPath('userData'), 'accounts.json') }
  get statsPath (): string { return join(app.getPath('userData'), 'stats.json') }

  async load (): Promise<void> {
    this.accounts = migrate(await readJson<unknown>(this.accountsPath, null))
    const rawStats = await readJson<StatsFile>(this.statsPath, emptyStats())
    const cutoff = new Date()
    cutoff.setDate(cutoff.getDate() - RETENTION_DAYS)
    this.stats = purgeOlderThan(rawStats, dayKey(cutoff))
  }

  async saveAccounts (): Promise<void> {
    await writeJsonAtomic(this.accountsPath, this.accounts)
  }

  async saveStats (): Promise<void> {
    if (!this.statsDirty) return
    await writeJsonAtomic(this.statsPath, this.stats)
    this.statsDirty = false
  }

  tick (seconds: number): void {
    if (this.focusedId === null) return
    this.stats = addSeconds(this.stats, dayKey(new Date()), this.focusedId, seconds)
    this.statsDirty = true
  }

  todaySeconds (): Record<string, number> {
    return this.stats.days[dayKey(new Date())] ?? {}
  }

  find (id: string): Account {
    const account = this.accounts.accounts.find(a => a.id === id)
    if (account === undefined) throw new Error(`compte introuvable : ${id}`)
    return account
  }
}

export function registerIpc (state: AppState, views: ViewManager): void {
  ipcMain.handle('accounts:list', () => state.accounts.accounts)

  ipcMain.handle('accounts:create', async (_event, label: string) => {
    state.accounts = createAccount(state.accounts, {
      id: randomUUID().slice(0, 8),
      label,
      createdAt: new Date().toISOString()
    })
    await state.saveAccounts()
    return state.accounts.accounts
  })

  ipcMain.handle('accounts:update', async (_event, id: string, patch: Record<string, unknown>) => {
    state.accounts = updateAccount(state.accounts, id, patch)
    await state.saveAccounts()
    return state.accounts.accounts
  })

  ipcMain.handle('accounts:delete', async (_event, id: string) => {
    const account = state.find(id)
    await views.destroy(account)
    if (state.focusedId === id) state.focusedId = null
    state.accounts = deleteAccount(state.accounts, id)
    await state.saveAccounts()
    return state.accounts.accounts
  })

  ipcMain.handle('view:start', async (_event, id: string) => {
    await views.start(state.find(id))
  })

  ipcMain.handle('view:stop', (_event, id: string) => {
    views.stop(id)
    if (state.focusedId === id) state.focusedId = null
  })

  ipcMain.handle('view:reload', (_event, id: string) => {
    views.reload(id)
  })

  ipcMain.handle('layout:apply', (_event, cells: CellRect[], focusedId: string | null) => {
    state.focusedId = focusedId
    views.applyLayout(cells, focusedId)
  })

  ipcMain.handle('stats:today', () => state.todaySeconds())
}
```

- [ ] **Step 3: Écrire le bootstrap**

`src/main/index.ts` :

```typescript
import { app, BaseWindow, WebContentsView, session } from 'electron'
import { join } from 'node:path'
import { AppState, registerIpc } from './ipc'
import { ViewManager } from './view-manager'
import { installProxyAuthHandler } from './session-manager'

const CHROME_PARTITION = 'chrome'
const state = new AppState()
const views = new ViewManager()

let window: BaseWindow | null = null
let chrome: WebContentsView | null = null

function createWindow (): void {
  window = new BaseWindow({ width: 1400, height: 900, title: 'TikTok Control Center' })

  // BaseWindow n'a pas de page hote : le chassis est lui-meme une vue, ajoutee
  // en premier pour rester sous les vues de comptes.
  chrome = new WebContentsView({
    webPreferences: {
      partition: CHROME_PARTITION,
      preload: join(__dirname, '../preload/index.js'),
      contextIsolation: true,
      nodeIntegration: false
    }
  })
  window.contentView.addChildView(chrome)
  // __dirname vaut dist/main a l'execution. Le HTML est *copie* vers
  // dist/renderer/index.html, alors que le TS compile vers
  // dist/renderer/renderer/main.js — d'ou le segment double dans le <script>
  // du HTML, mais pas ici.
  void chrome.webContents.loadFile(join(__dirname, '../renderer/index.html'))

  const fit = (): void => {
    const { width, height } = window!.getContentBounds()
    chrome!.setBounds({ x: 0, y: 0, width, height })
    // Le renderer recalcule et renvoie layout:apply ; les vues suivent.
    chrome!.webContents.send('window:resized', { width, height })
  }
  fit()
  window.on('resize', fit)

  views.attach(window)
  views.onStatus(event => chrome?.webContents.send('view:state', event))

  window.on('closed', () => {
    window = null
    chrome = null
  })
}

app.whenReady().then(async () => {
  await state.load()
  // Identite d'objet Session : `session.fromPartition` renvoie toujours la
  // meme instance pour une partition donnee. Comparaison exacte, la ou une
  // recherche de sous-chaine dans un chemin de stockage pouvait confondre
  // deux comptes.
  installProxyAuthHandler(ses =>
    state.accounts.accounts.find(a => session.fromPartition(a.partition) === ses))
  registerIpc(state, views)
  createWindow()

  // Le chrono n'avance que si l'application est au premier plan : une fenetre
  // laissee ouverte en arriere-plan ne doit pas gonfler les compteurs.
  setInterval(() => {
    if (!app.isReady() || window === null) return
    if (!window.isFocused()) return
    state.tick(1)
    chrome?.webContents.send('stats:tick', state.todaySeconds())
  }, 1000)

  setInterval(() => { void state.saveStats() }, 30_000)
})

app.on('before-quit', async event => {
  if (!state.statsDirty) return
  event.preventDefault()
  views.stopAll()
  await state.saveStats()
  app.quit()
})

app.on('window-all-closed', () => app.quit())
```

- [ ] **Step 4: Vérifier la compilation**

Run: `pnpm exec tsc -p tsconfig.json --noEmit`
Expected: aucune erreur.

- [ ] **Step 5: Committer**

```bash
git add src/main/index.ts src/main/ipc.ts src/preload/index.ts
git commit -m "feat: add main process bootstrap, ipc and preload bridge"
```

---

### Task 10: Le châssis — grille, en-têtes de cellule, focus

**Files:**
- Create: `src/renderer/index.html`
- Create: `src/renderer/styles.css`
- Create: `src/renderer/main.ts`
- Modify: `package.json` (copie du HTML et du CSS dans `dist/`)

**Interfaces:**
- Consumes: `window.api` (Task 9), `computeLayout`, `columnsFor` (Task 3), `PAGE_SIZE` (Task 2)
- Produces: l'interface utilisateur. Aucune autre tâche n'en dépend en code.

Le châssis dessine des cadres vides aux mêmes coordonnées que les vues natives, plus un bandeau d'en-tête au-dessus de chacun. Les vues de comptes recouvrent les cadres ; seul l'en-tête reste visible.

- [ ] **Step 1: Écrire le HTML**

`src/renderer/index.html` :

```html
<!doctype html>
<html lang="fr">
  <head>
    <meta charset="utf-8" />
    <title>TikTok Control Center</title>
    <link rel="stylesheet" href="styles.css" />
  </head>
  <body>
    <header id="toolbar">
      <h1>Control Center</h1>
      <form id="add-form">
        <input id="add-label" type="text" placeholder="@nom_du_compte" required />
        <button type="submit">Ajouter</button>
      </form>
      <nav id="pager" hidden>
        <button id="prev-page" type="button">&larr;</button>
        <span id="page-indicator"></span>
        <button id="next-page" type="button">&rarr;</button>
      </nav>
    </header>
    <main id="grid"></main>
    <p id="empty" hidden>Aucun compte. Ajoute-en un pour commencer.</p>
    <script type="module" src="renderer/main.js"></script>
  </body>
</html>
```

- [ ] **Step 2: Écrire le CSS**

`src/renderer/styles.css` :

```css
:root {
  --toolbar-height: 56px;
  --cell-header-height: 30px;
  --gap: 10px;
  --bg: #0f0f10;
  --panel: #1c1c1f;
  --text: #f1f1f2;
  --muted: #8a8a91;
  --accent: #fe2c55;
}

* { box-sizing: border-box; }

body {
  margin: 0;
  height: 100vh;
  overflow: hidden; /* le chassis ne scrolle jamais : les vues natives ne suivraient pas */
  background: var(--bg);
  color: var(--text);
  font: 13px/1.4 -apple-system, BlinkMacSystemFont, sans-serif;
}

#toolbar {
  height: var(--toolbar-height);
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 0 16px;
  background: var(--panel);
  border-bottom: 1px solid #2a2a2e;
}

#toolbar h1 { font-size: 14px; margin: 0; font-weight: 600; }
#add-form { display: flex; gap: 6px; }

input, button {
  font: inherit;
  border-radius: 6px;
  border: 1px solid #34343a;
  background: #26262b;
  color: var(--text);
  padding: 5px 10px;
}

button { cursor: pointer; }
button:hover { background: #34343a; }
#pager { margin-left: auto; display: flex; align-items: center; gap: 8px; }

#grid { position: relative; height: calc(100vh - var(--toolbar-height)); }

.cell {
  position: absolute;
  border: 1px solid #2a2a2e;
  border-radius: 8px;
  overflow: hidden;
  background: #000;
}

.cell.focused { border-color: var(--accent); }

.cell-header {
  height: var(--cell-header-height);
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 0 8px;
  background: var(--panel);
  cursor: pointer;
}

.cell-label { font-weight: 600; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.cell-timer { color: var(--muted); font-variant-numeric: tabular-nums; }
.cell-actions { margin-left: auto; display: flex; gap: 4px; }
.cell-actions button { padding: 1px 6px; font-size: 11px; }

.status { width: 7px; height: 7px; border-radius: 50%; flex: none; }
.status.stopped { background: #55555c; }
.status.loading { background: #e0a63a; }
.status.ready   { background: #3ecf6a; }
.status.error   { background: var(--accent); }

.cell-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  height: calc(100% - var(--cell-header-height));
  color: var(--muted);
}

#empty { position: absolute; inset: 0; display: grid; place-content: center; color: var(--muted); }
```

- [ ] **Step 3: Écrire la logique du renderer**

`src/renderer/main.ts` :

```typescript
import { computeLayout } from '../core/layout.js'
import { PAGE_SIZE } from '../core/types.js'
import type { Account, CellRect, ViewStatus } from '../core/types.js'

interface StatusEvent { id: string, status: ViewStatus, errorDescription?: string }

interface Api {
  listAccounts: () => Promise<Account[]>
  createAccount: (label: string) => Promise<Account[]>
  updateAccount: (id: string, patch: Record<string, unknown>) => Promise<Account[]>
  deleteAccount: (id: string) => Promise<Account[]>
  startView: (id: string) => Promise<void>
  stopView: (id: string) => Promise<void>
  reloadView: (id: string) => Promise<void>
  applyLayout: (cells: CellRect[], focusedId: string | null) => Promise<void>
  getStats: () => Promise<Record<string, number>>
  onStatus: (handler: (event: StatusEvent) => void) => void
  onStats: (handler: (seconds: Record<string, number>) => void) => void
}

declare global { interface Window { api: Api } }

const GAP = 10
const CELL_HEADER_HEIGHT = 30

const grid = document.getElementById('grid') as HTMLDivElement
const emptyNote = document.getElementById('empty') as HTMLParagraphElement
const pager = document.getElementById('pager') as HTMLElement
const pageIndicator = document.getElementById('page-indicator') as HTMLSpanElement

let accounts: Account[] = []
let statuses = new Map<string, ViewStatus>()
let seconds: Record<string, number> = {}
let focusedId: string | null = null
let pageIndex = 0

function currentPage (): Account[] {
  return accounts.slice(pageIndex * PAGE_SIZE, pageIndex * PAGE_SIZE + PAGE_SIZE)
}

function pageCount (): number {
  return Math.max(1, Math.ceil(accounts.length / PAGE_SIZE))
}

function formatDuration (total: number): string {
  const minutes = Math.floor(total / 60)
  return `${minutes}m`
}

/** Redessine le chassis et envoie la geometrie au main, qui deplace les vues natives. */
function render (): void {
  emptyNote.hidden = accounts.length > 0
  pager.hidden = accounts.length <= PAGE_SIZE
  pageIndicator.textContent = `${pageIndex + 1} / ${pageCount()}`

  const page = currentPage()
  const cells = computeLayout({
    ids: page.map(a => a.id),
    focusedId,
    viewport: { x: 0, y: 0, width: grid.clientWidth, height: grid.clientHeight },
    gap: GAP,
    cellHeaderHeight: CELL_HEADER_HEIGHT
  })

  grid.replaceChildren(...page.map(account => {
    const cell = cells.find(c => c.id === account.id)!
    return renderCell(account, cell)
  }))

  void window.api.applyLayout(cells, focusedId)
}

function renderCell (account: Account, cell: CellRect): HTMLElement {
  const status = statuses.get(account.id) ?? 'stopped'
  const element = document.createElement('div')
  element.className = `cell${account.id === focusedId ? ' focused' : ''}`
  // Le rectangle de la vue exclut l'en-tete : on le rajoute pour dessiner le cadre.
  element.style.left = `${cell.x}px`
  element.style.top = `${cell.y - CELL_HEADER_HEIGHT}px`
  element.style.width = `${cell.width}px`
  element.style.height = `${cell.height + CELL_HEADER_HEIGHT}px`

  const header = document.createElement('div')
  header.className = 'cell-header'
  header.addEventListener('click', () => {
    focusedId = focusedId === account.id ? null : account.id
    render()
  })

  const dot = document.createElement('span')
  dot.className = `status ${status}`

  const label = document.createElement('span')
  label.className = 'cell-label'
  label.textContent = account.label

  const timer = document.createElement('span')
  timer.className = 'cell-timer'
  const spent = seconds[account.id] ?? 0
  timer.textContent = `${formatDuration(spent)} / ${account.dailyGoalMinutes}m`

  const actions = document.createElement('div')
  actions.className = 'cell-actions'
  actions.append(
    actionButton(status === 'stopped' ? 'Démarrer' : 'Arrêter', async () => {
      if (status === 'stopped') await window.api.startView(account.id)
      else await window.api.stopView(account.id)
      render()
    }),
    actionButton('Recharger', async () => { await window.api.reloadView(account.id) }),
    actionButton('Supprimer', async () => {
      if (!confirm(`Supprimer ${account.label} et effacer sa session ?`)) return
      accounts = await window.api.deleteAccount(account.id)
      if (focusedId === account.id) focusedId = null
      if (currentPage().length === 0 && pageIndex > 0) pageIndex -= 1
      render()
    })
  )

  header.append(dot, label, timer, actions)
  element.append(header)

  if (status === 'stopped') {
    const placeholder = document.createElement('div')
    placeholder.className = 'cell-placeholder'
    placeholder.textContent = 'Session arrêtée'
    element.append(placeholder)
  }

  return element
}

function actionButton (text: string, onClick: () => void | Promise<void>): HTMLButtonElement {
  const button = document.createElement('button')
  button.type = 'button'
  button.textContent = text
  button.addEventListener('click', event => {
    event.stopPropagation() // sinon le clic remonte a l'en-tete et change le focus
    void onClick()
  })
  return button
}

document.getElementById('add-form')!.addEventListener('submit', async event => {
  event.preventDefault()
  const input = document.getElementById('add-label') as HTMLInputElement
  accounts = await window.api.createAccount(input.value.trim())
  input.value = ''
  render()
})

document.getElementById('prev-page')!.addEventListener('click', () => {
  pageIndex = Math.max(0, pageIndex - 1)
  focusedId = null
  render()
})

document.getElementById('next-page')!.addEventListener('click', () => {
  pageIndex = Math.min(pageCount() - 1, pageIndex + 1)
  focusedId = null
  render()
})

window.addEventListener('resize', render)

window.api.onStatus(event => {
  statuses.set(event.id, event.status)
  render()
})

window.api.onStats(payload => {
  seconds = payload
  // Mise a jour des seuls compteurs : un render complet a chaque seconde
  // reconstruirait le DOM et ferait clignoter l'interface.
  for (const account of currentPage()) {
    const cell = grid.querySelector(`.cell:nth-child(${currentPage().indexOf(account) + 1}) .cell-timer`)
    if (cell !== null) {
      cell.textContent = `${formatDuration(seconds[account.id] ?? 0)} / ${account.dailyGoalMinutes}m`
    }
  }
})

async function boot (): Promise<void> {
  accounts = await window.api.listAccounts()
  seconds = await window.api.getStats()
  render()
}

void boot()
```

- [ ] **Step 4: Copier le HTML et le CSS dans `dist/`**

`tsc` ne copie pas les fichiers non-TypeScript. Dans `package.json`, remplacer le script `build` par :

```json
    "build": "tsc -p tsconfig.json && tsc -p tsconfig.renderer.json && mkdir -p dist/renderer && cp src/renderer/index.html src/renderer/styles.css dist/renderer/",
```

Le HTML atterrit dans `dist/renderer/index.html` et le TypeScript compilé dans `dist/renderer/renderer/main.js` — d'où le `src="renderer/main.js"` de l'étape 1.

- [ ] **Step 5: Lancer l'application et vérifier à la main**

```bash
pnpm start
```

Vérifier :

1. La fenêtre s'ouvre avec la barre d'outils et le message « Aucun compte ».
2. Ajouter deux comptes : deux cadres apparaissent côte à côte, statut gris.
3. « Démarrer » sur l'un : TikTok se charge dans le cadre, la pastille passe au vert.
4. Cliquer sur un en-tête : la cellule s'agrandit, l'autre passe dans la colonne de droite, et les vues natives suivent exactement les cadres.
5. Scroller à la molette dans la cellule focalisée : le fil TikTok défile.
6. Redimensionner la fenêtre : les vues restent alignées sur leurs cadres.
7. Démarrer les deux : seule la cellule focalisée a le son.

- [ ] **Step 6: Committer**

```bash
git add src/renderer package.json
git commit -m "feat: add grid chrome with focus and per-cell controls"
```

---

### Task 11: Vérification d'isolation et de persistance

Le cœur de la promesse du produit — deux comptes qui ne se voient pas — ne peut se vérifier qu'à la main, avec de vrais comptes. Cette tâche n'écrit pas de code : elle vérifie, et documente le résultat.

**Files:**
- Create: `docs/verification.md`

**Interfaces:**
- Consumes: l'application complète (Tasks 1-10)
- Produces: rien en code. Une trace écrite de ce qui a été vérifié.

- [ ] **Step 1: Vérifier l'isolation des sessions**

1. Créer deux comptes, les démarrer tous les deux.
2. Se connecter à un compte TikTok différent dans chacun.
3. Vérifier que chaque cellule affiche bien **son** compte connecté (ouvrir le profil dans chacune).

Attendu : aucun croisement. Si les deux cellules montrent le même compte, les partitions ne sont pas appliquées — c'est bloquant.

- [ ] **Step 2: Vérifier la persistance**

1. Quitter l'application complètement.
2. La relancer, démarrer les deux cellules.

Attendu : les deux sessions sont toujours connectées, chacune sur son compte.

- [ ] **Step 3: Vérifier le chrono**

1. Focaliser une cellule, la laisser 2 minutes au premier plan.
2. Passer à une autre application 1 minute, revenir.

Attendu : le compteur de la cellule focalisée a avancé d'environ 2 minutes, pas 3. Le compteur des autres cellules n'a pas bougé.

- [ ] **Step 4: Vérifier la suppression**

1. Supprimer un compte, confirmer.
2. Le recréer avec le même libellé, le démarrer.

Attendu : la nouvelle cellule est **déconnectée** — la preuve que `clearStorageData` a bien effacé la session.

- [ ] **Step 5: Consigner le résultat**

Écrire dans `docs/verification.md` la date, la version d'Electron, et le résultat de chacune des quatre vérifications. Si l'une échoue, la décrire précisément plutôt que de passer à la suite.

- [ ] **Step 6: Committer**

```bash
git add docs/verification.md
git commit -m "docs: record manual isolation and persistence verification"
```

---

## Self-review

**Couverture du spec**

| Exigence du spec | Tâche |
| --- | --- |
| Prototype de validation en premier | Task 1 |
| `BaseWindow` + châssis en `WebContentsView` | Task 9 |
| Une `WebContentsView` et une partition par compte | Tasks 7, 8 |
| `src/core/` sans import Electron | Tasks 2-5, 7 (étape 3) |
| Grille fixe, pagination à 6 | Tasks 3, 10 |
| Scroll à l'intérieur des cellules | Natif — aucune interception ; vérifié Task 10 étape 5 |
| Focus : agrandissement et colonne de droite | Tasks 3, 10 |
| Chrono par compte, en pause hors premier plan | Task 9 (bootstrap), vérifié Task 11 |
| `accounts.json` / `stats.json` séparés, écriture atomique | Tasks 6, 9 |
| Purge au-delà de 90 jours | Task 9 (`AppState.load`) |
| User-agent sans jeton Electron | Task 7 |
| Champs `proxy` et `userAgent` lus dès la V1, sans UI | Tasks 5, 7 |
| Mise en sourdine et pause des cellules non focalisées | Task 8 |
| Suppression avec `clearStorageData` | Tasks 8, 9, vérifié Task 11 |
| Statut de vue et erreur non propagée | Task 8 |
| Aucune action automatisée | Contrainte globale ; aucune tâche n'introduit `sendInputEvent` |

Les notes et l'objectif quotidien sont **stockés et affichés** (le compteur `12m / 15m` de la Task 10) mais n'ont pas d'écran d'édition. C'est un écart assumé par rapport au spec, qui les listait en V1 : `updateAccount` est exposé par IPC, donc l'écran se rajoute sans changement d'architecture. À signaler à la revue de la Task 10.

**Cohérence des types** — `CellRect`, `Account`, `ViewStatus` et `StatsFile` sont définis une seule fois en Task 2 et importés partout. `computeLayout` a la même signature en Task 3 (définition), Task 9 (transport IPC) et Task 10 (appel). `partitionFor` est la seule source de la chaîne de partition, utilisée en Tasks 5, 7 et 8.

**Placeholders** — aucun « TBD », aucune étape sans code, aucune référence à une fonction non définie.
