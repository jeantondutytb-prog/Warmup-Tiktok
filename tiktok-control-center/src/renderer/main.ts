import { computeLayout } from '../core/layout.js'
import { PAGE_SIZE, PORTRAIT_ASPECT } from '../core/types.js'
import type { Account, CellRect, StatsFile, ViewStatus } from '../core/types.js'
import { dayKey, emptyStats } from '../core/stats.js'
import { nextUp, regularityScore } from '../core/pilot.js'
import type { PilotEntry } from '../core/pilot.js'

interface StatusEvent { id: string, status: ViewStatus, errorDescription?: string }

interface Api {
  listAccounts: () => Promise<Account[]>
  createAccount: (label: string) => Promise<Account[]>
  updateAccount: (id: string, patch: Record<string, unknown>) => Promise<Account[]>
  deleteAccount: (id: string) => Promise<Account[]>
  startView: (id: string) => Promise<void>
  stopView: (id: string) => Promise<void>
  reloadView: (id: string) => Promise<void>
  focusView: (id: string) => Promise<void>
  applyLayout: (cells: CellRect[], focusedId: string | null) => Promise<void>
  getStats: () => Promise<Record<string, number>>
  getFullStats: () => Promise<StatsFile>
  onStatus: (handler: (event: StatusEvent) => void) => void
  onStats: (handler: (seconds: Record<string, number>) => void) => void
}

declare global { interface Window { api: Api } }

const GAP = 10
const CELL_HEADER_HEIGHT = 30
// Combien de temps un message d'erreur reste affiche avant de s'effacer tout seul.
const ERROR_DISPLAY_MS = 5000

const grid = document.getElementById('grid') as HTMLDivElement
// Conteneur dedie aux cellules, distinct de #empty : #empty vit aussi dans
// #grid (pour que son "inset: 0" reste borne a la zone grille et ne
// recouvre jamais la barre d'outils), et grid.replaceChildren() dans
// render() detruirait #empty s'il ciblait #grid directement.
const cellsContainer = document.getElementById('cells') as HTMLDivElement
const emptyNote = document.getElementById('empty') as HTMLParagraphElement
const pager = document.getElementById('pager') as HTMLElement
const pageIndicator = document.getElementById('page-indicator') as HTMLSpanElement
const errorBanner = document.getElementById('error-banner') as HTMLDivElement
const pilotStrip = document.getElementById('pilot') as HTMLDivElement
const pilotText = document.getElementById('pilot-text') as HTMLSpanElement
const pilotGoButton = document.getElementById('pilot-go') as HTMLButtonElement

let accounts: Account[] = []
let statuses = new Map<string, ViewStatus>()
let seconds: Record<string, number> = {}
// Historique complet (stats:full), distinct de `seconds` (stats:today) : seul
// nextUp() en a besoin (fenetre glissante de pilot.WINDOW_DAYS jours, derniere
// session active). Tenu a jour a la volee dans onStats plutot que refetch,
// voir ce site d'appel.
let fullStats: StatsFile = emptyStats()
let focusedId: string | null = null
let pageIndex = 0
// Entree la plus prioritaire de nextUp(), ou null s'il n'y a aucun compte.
// Recalculee par renderPilot(), lue par le clic sur #pilot-go.
let pilotEntry: PilotEntry | null = null

/**
 * Seul site qui doit ecrire `focusedId` : centraliser l'affectation permet de
 * ne demander le focus clavier OS (window.api.focusView) que lorsque le
 * compte focalise change reellement, jamais a chaque appel de render() (qui
 * s'execute a chaque evenement de statut/stats). Sans cette garde, chaque
 * render() volerait le focus a ce que l'utilisateur est en train de faire —
 * y compris un champ texte TikTok en cours de saisie. Un focusedId qui
 * redevient null n'a rien a focaliser cote natif : on se contente alors de
 * mettre a jour l'etat local.
 */
function setFocusedId (id: string | null): void {
  if (id === focusedId) return
  focusedId = id
  if (id !== null) void window.api.focusView(id)
}

// --- Etat du bandeau d'erreur -------------------------------------------
// Le bandeau est *derive* de cet etat par renderBanner(), jamais mute
// directement par un site d'appel : sinon un message transitoire (ex.
// "Demarrer" rate) ecrase inconditionnellement un message persistant
// toujours vrai (ex. chargement initial rate), qui disparait alors avec le
// minuteur du toast sans que la condition sous-jacente soit resolue.
//
// Priorite d'affichage quand plusieurs conditions sont vraies en meme temps
// (la plus severe gagne, et resoudre la plus severe re-decouvre les
// suivantes au prochain renderBanner()) :
//   1. accountsError  - rien n'a pu etre charge, l'app est quasi inutilisable
//   2. statsError     - les comptes sont la, seuls les temps sont indisponibles
//   3. layoutError    - les comptes et temps sont bons, seul l'alignement
//                        cadres/vues natives est en cause
//   4. transientError - evenement ponctuel (ex. une action a echoue)
// Resoudre ou fermer une condition ne touche qu'a sa propre variable : les
// trois autres restent inchangees.
let accountsError: string | null = null
let statsError: string | null = null
let layoutError: string | null = null
let transientError: { message: string, retry?: () => void } | null = null
let transientTimer: ReturnType<typeof setTimeout> | null = null

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

function describeError (error: unknown): string {
  return error instanceof Error ? error.message : String(error)
}

function paintBanner (
  message: string, options: { persistent: boolean, retry?: () => void, dismiss?: () => void }
): void {
  errorBanner.replaceChildren()

  const text = document.createElement('span')
  text.className = 'error-text'
  text.textContent = message
  errorBanner.append(text)

  if (options.retry !== undefined) {
    const retryButton = document.createElement('button')
    retryButton.type = 'button'
    retryButton.textContent = 'Réessayer'
    retryButton.addEventListener('click', () => { options.retry!() })
    errorBanner.append(retryButton)
  }

  if (options.persistent && options.dismiss !== undefined) {
    const dismissButton = document.createElement('button')
    dismissButton.type = 'button'
    dismissButton.textContent = '✕'
    dismissButton.setAttribute('aria-label', 'Fermer le message')
    dismissButton.addEventListener('click', () => { options.dismiss!() })
    errorBanner.append(dismissButton)
  }

  errorBanner.hidden = false
}

/**
 * Seule fonction qui touche `errorBanner` en dehors de paintBanner() : elle
 * lit l'etat (accountsError/statsError/layoutError/transientError) et decide
 * quoi afficher, selon la priorite documentee plus haut. Aucun site d'appel
 * ne doit manipuler `errorBanner` directement.
 */
function renderBanner (): void {
  if (accountsError !== null) {
    paintBanner(`Impossible de charger les comptes : ${accountsError}`, {
      persistent: true,
      retry: () => { void boot() },
      dismiss: () => { accountsError = null; renderBanner() }
    })
    return
  }
  if (statsError !== null) {
    paintBanner(`Temps passé indisponible, les compteurs resteront à 0 : ${statsError}`, {
      persistent: true,
      retry: () => { void boot() },
      dismiss: () => { statsError = null; renderBanner() }
    })
    return
  }
  if (layoutError !== null) {
    paintBanner(`Les cadres affichés ne correspondent plus aux vues natives : ${layoutError}`, {
      persistent: true,
      retry: () => { render() },
      dismiss: () => { layoutError = null; renderBanner() }
    })
    return
  }
  if (transientError !== null) {
    paintBanner(transientError.message, { persistent: false, retry: transientError.retry })
    return
  }
  errorBanner.hidden = true
}

/**
 * Message ponctuel (ex. une action a echoue) : s'efface tout seul apres
 * ERROR_DISPLAY_MS. Le minuteur n'efface que `transientError`, jamais le
 * bandeau lui-meme, puis rappelle renderBanner() - si une condition
 * persistante est (ou est devenue) vraie entretemps, elle reapparait au lieu
 * de laisser le bandeau vide.
 */
function setTransientError (message: string, retry?: () => void): void {
  transientError = { message, retry }
  if (transientTimer !== null) clearTimeout(transientTimer)
  transientTimer = setTimeout(() => {
    transientError = null
    transientTimer = null
    renderBanner()
  }, ERROR_DISPLAY_MS)
  renderBanner()
}

/**
 * Envoie la geometrie au main pour que les vues natives suivent les cadres.
 * Si l'appel rejette on retente une fois immediatement (la panne est souvent
 * transitoire) ; s'il rejette encore, le desync cadres/vues est un etat -
 * pas un evenement ponctuel - donc on le signale via layoutError, dont
 * renderBanner() fait un bandeau persistant plutot qu'un toast qui
 * disparaitrait en laissant l'ecran mentir.
 */
function applyLayoutToNative (cells: CellRect[], focused: string | null, isRetry = false): void {
  window.api.applyLayout(cells, focused)
    .then(() => {
      if (layoutError !== null) {
        layoutError = null
        renderBanner()
      }
    })
    .catch((error: unknown) => {
      if (!isRetry) {
        applyLayoutToNative(cells, focused, true)
        return
      }
      layoutError = describeError(error)
      renderBanner()
    })
}

/** Redessine le chassis et envoie la geometrie au main, qui deplace les vues natives. */
function render (): void {
  emptyNote.hidden = accounts.length > 0
  pager.hidden = accounts.length <= PAGE_SIZE
  pageIndicator.textContent = `${pageIndex + 1} / ${pageCount()}`

  const page = currentPage()
  // #grid est place sous #toolbar dans la page chassis ; comme cette page
  // remplit la fenetre, ses coordonnees client partagent l'origine de la
  // fenetre. On mesure donc une seule fois le decalage reel du grid (plutot
  // que de coder en dur la hauteur de la barre d'outils) et on l'utilise a
  // la fois comme origine du viewport natif (espace fenetre, pour
  // setBounds) et pour ramener les cadres CSS en espace local au grid.
  const rect = grid.getBoundingClientRect()
  const cells = computeLayout({
    ids: page.map(a => a.id),
    focusedId,
    viewport: { x: rect.left, y: rect.top, width: rect.width, height: rect.height },
    gap: GAP,
    cellHeaderHeight: CELL_HEADER_HEIGHT,
    aspectRatio: PORTRAIT_ASPECT
  })

  cellsContainer.replaceChildren(...page.map(account => {
    const cell = cells.find(c => c.id === account.id)!
    return renderCell(account, cell, rect)
  }))

  applyLayoutToNative(cells, focusedId)
}

function renderCell (account: Account, cell: CellRect, gridRect: DOMRect): HTMLElement {
  const status = statuses.get(account.id) ?? 'stopped'
  const element = document.createElement('div')
  element.className = `cell${account.id === focusedId ? ' focused' : ''}`
  element.dataset.accountId = account.id
  // cell.x/cell.y sont en espace fenetre (ils incluent le decalage du grid,
  // requis par setBounds) ; on le retranche pour revenir en espace local au
  // grid, seul repere valable pour des elements positionnes en absolute a
  // l'interieur de #grid. Le rectangle de la vue exclut l'en-tete : on le
  // rajoute pour dessiner le cadre.
  element.style.left = `${cell.x - gridRect.left}px`
  element.style.top = `${cell.y - gridRect.top - CELL_HEADER_HEIGHT}px`
  element.style.width = `${cell.width}px`
  element.style.height = `${cell.height + CELL_HEADER_HEIGHT}px`

  const header = document.createElement('div')
  header.className = 'cell-header'
  header.addEventListener('click', () => {
    setFocusedId(focusedId === account.id ? null : account.id)
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

  // Score de REGULARITE du proprietaire (assiduite/tenue d'objectif), pas un
  // avis TikTok sur le compte - voir la jsdoc de regularityScore. Terse par
  // necessite : l'en-tete est deja charge, cf. le titre pour le detail.
  const score = document.createElement('span')
  score.className = 'cell-score'
  score.title = 'Score de régularité (constance du propriétaire, pas un avis TikTok)'
  score.textContent = `${regularityScore(account, fullStats, new Date())}`

  const actions = document.createElement('div')
  actions.className = 'cell-actions'
  actions.append(
    actionButton(status === 'stopped' ? 'Démarrer' : 'Arrêter', async () => {
      try {
        if (status === 'stopped') await window.api.startView(account.id)
        else await window.api.stopView(account.id)
      } catch (error) {
        setTransientError(`Action impossible sur ${account.label} : ${describeError(error)}`)
      }
      render()
    }),
    actionButton('Recharger', async () => {
      try {
        await window.api.reloadView(account.id)
      } catch (error) {
        setTransientError(`Impossible de recharger ${account.label} : ${describeError(error)}`)
      }
    }),
    actionButton('Supprimer', async () => {
      if (!confirm(`Supprimer ${account.label} et effacer sa session ?`)) return
      try {
        accounts = await window.api.deleteAccount(account.id)
        if (focusedId === account.id) setFocusedId(null)
        if (currentPage().length === 0 && pageIndex > 0) pageIndex -= 1
        render()
        renderPilot()
      } catch (error) {
        setTransientError(`Impossible de supprimer ${account.label} : ${describeError(error)}`)
      }
    })
  )

  header.append(dot, label, timer, score, actions)
  element.append(header)

  if (status === 'stopped') {
    const placeholder = document.createElement('div')
    placeholder.className = 'cell-placeholder'
    placeholder.textContent = 'Session arrêtée'
    element.append(placeholder)
  }

  return element
}

/** "3 j sans session" / "jamais lancé" / "actif aujourd'hui" pour daysSinceLastSession. */
function formatNeglect (days: number | null): string {
  if (days === null) return 'jamais lancé'
  if (days === 0) return "actif aujourd'hui"
  return `${days} j sans session`
}

/**
 * Redessine uniquement le bandeau pilote (texte + visibilite), jamais la
 * grille : appelee au boot, a chaque ajout/suppression de compte et a chaque
 * tick de stats (via onStats, cf. plus bas), elle ne doit pas re-executer
 * render() - qui reconstruit les cellules et redeplace les vues natives,
 * source du clignotement que la mise a jour ciblee des minuteurs evite deja.
 */
function renderPilot (): void {
  pilotEntry = nextUp(accounts, fullStats, new Date())[0] ?? null
  // Aucun compte : rien a piloter, degrade en repliant simplement le bandeau
  // plutot que d'afficher un texte vide.
  pilotStrip.hidden = pilotEntry === null
  if (pilotEntry === null) return
  const { account, daysSinceLastSession, secondsToday } = pilotEntry
  pilotText.textContent =
    `Prochain : ${account.label} — ${formatNeglect(daysSinceLastSession)} · ${formatDuration(secondsToday)} / ${account.dailyGoalMinutes}m`
}

/**
 * Action du bouton "Y aller" : meme cible que le clic sur l'en-tete d'une
 * cellule (setFocusedId, donc window.api.focusView), avec la meme garde
 * contre le rejet que les boutons d'action existants (cf. actionButton) -
 * aucune logique de focus/demarrage dupliquee, seulement reutilisee. Deux
 * ajouts propres au pilote : basculer sur la page qui contient le compte (il
 * peut etre hors page courante) et le demarrer d'abord s'il est arrete.
 */
async function goToAccount (id: string): Promise<void> {
  const index = accounts.findIndex(a => a.id === id)
  if (index === -1) return

  pageIndex = Math.floor(index / PAGE_SIZE)

  if ((statuses.get(id) ?? 'stopped') === 'stopped') {
    try {
      await window.api.startView(id)
    } catch (error) {
      setTransientError(`Action impossible sur ${accounts[index].label} : ${describeError(error)}`)
    }
  }

  setFocusedId(id)
  render()
}

pilotGoButton.addEventListener('click', () => {
  if (pilotEntry !== null) void goToAccount(pilotEntry.account.id)
})

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
  try {
    accounts = await window.api.createAccount(input.value.trim())
    input.value = ''
    render()
    renderPilot()
  } catch (error) {
    setTransientError(`Impossible d'ajouter le compte : ${describeError(error)}`)
  }
})

document.getElementById('prev-page')!.addEventListener('click', () => {
  pageIndex = Math.max(0, pageIndex - 1)
  setFocusedId(null)
  render()
})

document.getElementById('next-page')!.addEventListener('click', () => {
  pageIndex = Math.min(pageCount() - 1, pageIndex + 1)
  setFocusedId(null)
  render()
})

window.addEventListener('resize', render)

// Enregistres une seule fois, au demarrage : ni onStatus ni onStats n'ont de
// voie de desabonnement, donc les rebrancher depuis render() (qui s'execute
// a chaque interaction) empilerait un ecouteur de plus a chaque fois.
window.api.onStatus(event => {
  statuses.set(event.id, event.status)
  render()
})

window.api.onStats(payload => {
  seconds = payload
  // stats:tick ne porte que le total du jour courant (meme forme que
  // stats:today) : on le refond dans la copie locale de l'historique complet
  // plutot que d'ajouter un aller-retour IPC dedie, pour que nextUp() (via
  // renderPilot() et le score par cellule ci-dessous) reste a jour seconde
  // par seconde sans nouveau canal.
  fullStats = { ...fullStats, days: { ...fullStats.days, [dayKey(new Date())]: payload } }

  // Mise a jour des seuls compteurs/scores, retrouves via data-account-id : un
  // render complet a chaque seconde reconstruirait le DOM et ferait clignoter
  // l'interface, et un index base sur l'ordre de page se desynchroniserait
  // des que cet ordre change. Meme discipline pour le bandeau pilote : voir
  // renderPilot(), qui ne touche pas non plus a la grille.
  for (const cellElement of cellsContainer.children) {
    const id = (cellElement as HTMLElement).dataset.accountId
    if (id === undefined) continue
    const account = accounts.find(a => a.id === id)
    if (account === undefined) continue
    const timer = cellElement.querySelector('.cell-timer')
    if (timer !== null) {
      timer.textContent = `${formatDuration(seconds[id] ?? 0)} / ${account.dailyGoalMinutes}m`
    }
    const score = cellElement.querySelector('.cell-score')
    if (score !== null) {
      score.textContent = `${regularityScore(account, fullStats, new Date())}`
    }
  }

  renderPilot()
})

/**
 * listAccounts()/getStats()/getFullStats() sont des lectures, mais un rejet
 * ici est le pire cas de tous : sans filet, render() ne serait jamais atteint
 * et l'utilisateur verrait une fenetre vide, sans chassis ni bandeau,
 * indiscernable d'un lancement fige. Les trois appels sont gardes
 * independamment (Promise.allSettled, pas un seul try/catch) : si les comptes
 * chargent mais pas les stats, on garde la liste de comptes reussie plutot
 * que de la jeter juste parce que les temps ont echoue - une grille avec des
 * compteurs a 0 est comprehensible, une grille vide qui contenait des comptes
 * une seconde plus tot lit comme "mes comptes ont disparu". getStats() et
 * getFullStats() partagent statsError (meme famille de panne - "le temps
 * passe est indisponible" - deja modelisee par le bandeau existant) plutot
 * que d'ajouter un nouvel etat au modele du bandeau pour la seule fenetre de
 * pilotage.
 */
async function boot (): Promise<void> {
  const [accountsResult, statsResult, fullStatsResult] = await Promise.allSettled([
    window.api.listAccounts(),
    window.api.getStats(),
    window.api.getFullStats()
  ])

  if (accountsResult.status === 'fulfilled') {
    accounts = accountsResult.value
    accountsError = null
  } else {
    accounts = []
    accountsError = describeError(accountsResult.reason)
  }

  if (statsResult.status === 'fulfilled' && fullStatsResult.status === 'fulfilled') {
    seconds = statsResult.value
    fullStats = fullStatsResult.value
    statsError = null
  } else {
    seconds = statsResult.status === 'fulfilled' ? statsResult.value : {}
    fullStats = fullStatsResult.status === 'fulfilled' ? fullStatsResult.value : emptyStats()
    const failure = statsResult.status === 'rejected' ? statsResult.reason : (fullStatsResult as PromiseRejectedResult).reason
    statsError = describeError(failure)
  }

  renderBanner()
  render()
  renderPilot()
}

void boot()
