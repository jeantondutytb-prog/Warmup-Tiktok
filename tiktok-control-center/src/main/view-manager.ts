import { WebContentsView } from 'electron'
import type { BaseWindow } from 'electron'
import { configureSession, destroySession } from './session-manager'
import { PAUSE_VIDEOS_SCRIPT } from '../core/pause-videos-script'
import { isAllowedNavigationTarget, isAllowedPopupTarget } from '../core/navigation-guard'
import type { Account, CellRect, ViewStatus } from '../core/types'

const HIDDEN: CellRect = { id: '', x: 0, y: 0, width: 0, height: 0 }

/** Evenements dont ViewManager branche un ecouteur sur chaque webContents.
 *  Liste unique partagee entre le branchement (wireStatusEvents) et le
 *  debranchement (teardownView), pour que les deux ne puissent pas diverger. */
const STATUS_EVENTS = ['did-start-loading', 'did-finish-load', 'did-fail-load'] as const

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
  // Ids dont le demarrage est en cours, entre l'appel synchrone et la premiere
  // await : reserve la place avant meme que `views` ne connaisse la vue, pour
  // qu'un second `start()` concurrent sur le meme compte ne cree pas une
  // seconde vue orpheline.
  private readonly starting = new Set<string>()
  // Ids dont le demarrage en cours a ete annule par un stop()/destroy() qui
  // est arrive pendant l'attente. Consulte par start() apres chaque await.
  private readonly cancelled = new Set<string>()
  // Promesse du start() en cours pour un id, pour que destroy() puisse
  // attendre qu'il se soit acheve (normalement ou par annulation) avant
  // d'effacer les donnees de la session.
  private readonly startPromises = new Map<string, Promise<void>>()
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
    const win = this.window
    if (win === null) throw new Error('ViewManager non attache a une fenetre')
    // `views.has` seul ne suffit pas : il ne devient vrai qu'apres la premiere
    // await ci-dessous, donc un second appel concurrent le traverserait aussi.
    // `starting` ferme cette fenetre en reservant la place de facon synchrone.
    if (this.views.has(account.id) || this.starting.has(account.id)) return

    this.starting.add(account.id)
    const task = this.runStart(account, win)
    this.startPromises.set(account.id, task)
    try {
      await task
    } finally {
      // Toujours liberer la reservation, y compris en cas d'echec ou
      // d'annulation, pour qu'un nouvel appel a start() puisse retenter.
      this.starting.delete(account.id)
      this.cancelled.delete(account.id)
      this.startPromises.delete(account.id)
    }
  }

  /**
   * Corps effectif de start(), avec un point de controle d'annulation apres
   * chaque await : un stop()/destroy() arrive pendant l'attente n'agit pas
   * directement sur une vue qui n'existe pas encore (ou qui n'est plus
   * a jour), il se contente de marquer `cancelled` ; c'est ici qu'on le
   * constate et qu'on demonte proprement ce qui a ete construit entre-temps.
   */
  private async runStart (account: Account, win: BaseWindow): Promise<void> {
    await configureSession(account)
    if (this.cancelled.has(account.id)) {
      // Aucune vue n'existe encore : rien a demonter, juste refleter l'arret.
      this.setStatus(account.id, 'stopped', '', '')
      return
    }

    const view = new WebContentsView({
      webPreferences: {
        partition: account.partition,
        contextIsolation: true,
        nodeIntegration: false
      }
    })

    this.wireStatusEvents(account.id, view)
    this.wireNavigationGuards(account.id, view)
    this.views.set(account.id, view)
    // Hors ecran jusqu'au premier applyLayout, pour eviter un flash en haut a gauche.
    view.setBounds(HIDDEN)
    win.contentView.addChildView(view)

    // Si loadURL echoue pour une raison ordinaire (pas une annulation), la vue
    // reste en place : did-fail-load (branche par wireStatusEvents ci-dessus)
    // l'a deja fait passer en statut 'error', et elle est recuperable via
    // reload() sans reconstruire ni reconfigurer la session. La detruire ici
    // perdrait cette information au profit d'un simple statut 'stopped' moins
    // parlant pour l'utilisateur.
    await view.webContents.loadURL('https://www.tiktok.com/')

    if (this.cancelled.has(account.id)) {
      // stop()/destroy() est arrive pendant le chargement : la vue est deja
      // enregistree et attachee, on annule exactement ce que start() a fait,
      // sans laisser echapper de statut 'ready' pour un id que l'appelant
      // croit deja arrete.
      this.teardownView(account.id, view, win)
    }
  }

  stop (id: string): void {
    if (this.starting.has(id)) {
      // Le demarrage n'a pas encore produit de vue exploitable (ou vient tout
      // juste d'en attacher une) : on ne peut rien demonter de synchrone ici.
      // On se contente d'enregistrer l'annulation ; runStart() la constatera
      // a son prochain point de controle et fera le menage lui-meme.
      this.cancelled.add(id)
      return
    }
    const view = this.views.get(id)
    const win = this.window
    if (view === undefined || win === null) return
    this.teardownView(id, view, win)
  }

  reload (id: string): void {
    this.views.get(id)?.webContents.reload()
  }

  /**
   * Donne le focus clavier OS a la vue d'un compte, exactement comme un clic
   * de l'utilisateur dans la vue le ferait — ce n'est pas de la saisie
   * synthetique, seul le focus se deplace, aucune touche n'est envoyee. Sans
   * cela les fleches ↑/↓ et les raccourcis de TikTok n'atteignent jamais la
   * page malgre le focus "logique" pose cote chassis.
   *
   * `starting` couvre aussi bien l'id absent de `views` (la vue n'existe pas
   * encore) que l'id deja enregistre mais dont le chargement n'est pas
   * termine (voir runStart) : dans les deux cas il n'y a rien de fiable a
   * focaliser, donc on ne fait rien plutot que de risquer un focus qui serait
   * ecrase par la suite du demarrage.
   */
  focus (id: string): void {
    if (this.starting.has(id)) return
    const view = this.views.get(id)
    if (view === undefined) return
    view.webContents.focus()
  }

  async destroy (account: Account): Promise<void> {
    if (this.starting.has(account.id)) {
      this.cancelled.add(account.id)
      // Attendre que le start() en cours se soit reellement acheve (succes,
      // echec ou annulation) avant de toucher a la session : sans cela,
      // clearStorageData() pourrait s'executer pendant que configureSession()
      // ou loadURL() utilisent encore la meme partition.
      const pending = this.startPromises.get(account.id)
      if (pending !== undefined) await pending.catch(() => {})
    }
    // Idempotent : si runStart() a deja tout demonte suite a l'annulation
    // ci-dessus, `views` ne contient plus rien pour cet id et stop() ne fait
    // rien. Si le start() en cours a echoue pour une raison ordinaire (pas
    // une annulation), la vue est restee enregistree (cf. runStart) et doit
    // encore etre fermee avant d'effacer son stockage.
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
      await view.webContents.executeJavaScript(PAUSE_VIDEOS_SCRIPT)
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
      // Passe par setStatus (comme les deux ecouteurs ci-dessus) pour beneficier
      // du meme garde-fou contre les emissions perimees d'un start() annule.
      this.setStatus(id, 'error', validatedURL, '', errorCode, errorDescription)
    })
  }

  /**
   * TikTok est un site tiers que nous ne controlons pas : sa page peut a tout
   * moment tenter de faire echapper la vue de son role (ejecter l'utilisateur
   * vers l'App Store, ouvrir une fenetre en dehors de la grille, naviguer
   * hors de tiktok.com). Trois garde-fous, tous fondes sur les fonctions
   * pures de src/core/navigation-guard (testables sans Electron) :
   *
   * 1. `will-navigate` (navigation de la frame principale initiee par la
   *    page, pas par loadURL) est l'evenement recommande par la doc Electron
   *    elle-meme pour ce cas precis (docs/tutorial/security.md, section
   *    "Disable or limit navigation") : verifier `parsedUrl.origin`/hostname
   *    plutot qu'une comparaison de chaine, exactement ce que
   *    isAllowedNavigationTarget fait via URL parsing + suffixe sur le
   *    hostname (voir hostMatches). `will-redirect` n'a pas ete retenu :
   *    il se declenche aussi pour des redirections serveur legitimes
   *    (CDN, chainage OAuth) qu'on ne veut pas casser, et l'incident observe
   *    (bascule vers l'App Store) est une navigation, pas une redirection
   *    serveur. `will-frame-navigate` couvre en plus les sous-frames, qu'on
   *    n'a pas besoin de gouverner ici : aucune sous-frame TikTok ne pilote
   *    la cellule entiere. Cette meme ecoute couvre a la fois le garde-fou
   *    "schema non web" (isAllowedProtocol, evalue par isAllowedNavigationTarget)
   *    et le garde-fou "hors domaine TikTok" : les deux repondent a la meme
   *    question ("cette destination est-elle autorisee ?") sur le meme
   *    evenement.
   * 2. `setWindowOpenHandler` decide de toute fenetre/onglet demande par
   *    `window.open()` ou un lien `target="_blank"`. Retourner
   *    `{ action: 'deny' }` empeche la creation ; ne rien retourner ou
   *    renvoyer une valeur non reconnue est aussi traite comme un refus par
   *    Electron, mais on est explicite. La connexion TikTok peut passer par
   *    une popup (boutons "Continuer avec Google/Apple/Facebook") : plutot
   *    que de tout bloquer et casser silencieusement la connexion, seules
   *    les popups vers un fournisseur de connexion tierce connu sont
   *    autorisees (isAllowedPopupTarget) ; Electron ouvre alors une fenetre
   *    par defaut (hors de la grille geree par ViewManager, donc sans toucher
   *    a sa geometrie), ce qui correspond au comportement habituel d'un
   *    popup OAuth. Toute autre demande de fenetre (pub, "ouvrir dans
   *    l'appli", etc.) est refusee.
   * 3. Signalement : aucune emission via onStatus/StatusEvent ici — ce canal
   *    modelise le cycle de vie de la vue (stopped/loading/ready/error) que
   *    ce projet ne doit pas modifier, et un blocage de navigation ne change
   *    en rien ce cycle (la vue reste `ready`, la video continue). Un
   *    console.warn (meme canal que les autres echecs de fond du projet, ex.
   *    index.ts/ipc.ts) donne une trace diagnosticable sans inventer de
   *    nouvelle surface d'UI ni detourner un etat existant vers un sens qui
   *    ne serait plus le sien.
   */
  private wireNavigationGuards (id: string, view: WebContentsView): void {
    const { webContents } = view

    webContents.on('will-navigate', (event, url) => {
      if (isAllowedNavigationTarget(url)) return
      event.preventDefault()
      console.warn(`[view-manager] navigation bloquee pour le compte ${id} vers ${url}`)
    })

    webContents.setWindowOpenHandler(({ url }) => {
      if (isAllowedPopupTarget(url)) return { action: 'allow' }
      console.warn(`[view-manager] ouverture de fenetre bloquee pour le compte ${id} vers ${url}`)
      return { action: 'deny' }
    })
  }

  /**
   * Detache, ferme et oublie une vue. Utilise a la fois par stop() et par
   * runStart() quand un demarrage en cours est annule.
   *
   * Ne retire que les ecouteurs que wireStatusEvents a branches (STATUS_EVENTS),
   * pas `removeAllListeners()` sans argument : Electron peut brancher ses
   * propres ecouteurs internes sur ce webContents, et les retirer en bloc est
   * un piege connu (electron/electron#10379, #22290). Se limiter aux trois
   * evenements qu'on a nous-memes ajoutes suffit a garantir qu'aucun evenement
   * de statut ne peut plus etre emis pour `id` une fois cette methode revenue.
   */
  private teardownView (id: string, view: WebContentsView, win: BaseWindow): void {
    for (const event of STATUS_EVENTS) view.webContents.removeAllListeners(event)
    win.contentView.removeChildView(view)
    view.webContents.close()
    this.views.delete(id)
    this.setStatus(id, 'stopped', '', '')
  }

  /**
   * Point de passage unique pour toute emission de statut (les trois
   * ecouteurs de wireStatusEvents, et l'emission deliberee de 'stopped' dans
   * teardownView / runStart). Un start() annule ne doit plus faire progresser
   * l'etat public de la vue vers 'loading'/'ready'/'error' : did-finish-load
   * (et, plus rarement, did-start-loading/did-fail-load sur une redirection)
   * peut se declencher pendant la fenetre entre l'annulation et le prochain
   * point de controle de runStart, avant que la vue ne soit demontee — donc
   * apres coup du point de vue de l'appelant qui a deja demande l'arret.
   * Seule l'emission de 'stopped' passe pendant l'annulation : c'est elle qui
   * la cloture, et la supprimer laisserait le dernier statut visible etre
   * 'loading'/'ready'/'error' pour une vue en realite arretee.
   */
  private setStatus (id: string, status: ViewStatus, url: string, title: string, errorCode?: number, errorDescription?: string): void {
    if (this.cancelled.has(id) && status !== 'stopped') return
    this.statuses.set(id, status)
    this.listener({ id, status, url, title, errorCode, errorDescription })
  }
}
