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
  void chrome.webContents.loadFile(join(__dirname, '../renderer/index.html'))

  const fit = (): void => {
    const { width, height } = window!.getContentBounds()
    // Redimensionner la vue chrome declenche un evenement DOM 'resize' natif
    // dans sa propre page ; le renderer y reagit directement (pas d'IPC ici :
    // contextIsolation ne l'exposerait pas de toute facon, seuls onStatus et
    // onStats sont brancheables depuis le preload).
    chrome!.setBounds({ x: 0, y: 0, width, height })
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
  try {
    await state.load()
  } catch (error) {
    // migrateStats/migrate ne levent normalement jamais, mais une defaillance
    // imprevue ici (I/O, etc.) ne doit pas empecher la fenetre de s'ouvrir :
    // un utilisateur qui voit l'appli avec une liste de comptes vide peut se
    // reconstruire, un utilisateur qui ne voit rien du tout ne peut rien
    // diagnostiquer. On journalise et on poursuit avec l'etat par defaut
    // (AppState demarre deja avec emptyAccounts()/emptyStats()).
    console.error('echec du chargement de l\'etat au demarrage, poursuite avec un etat vide :', error)
  }
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
    // views.has() est l'autorite sur ce qui est reellement affiche : focusedId
    // peut devenir perime (ex. accounts:delete dont le teardown de la vue a
    // reussi mais dont l'effacement de session a echoue en cours de route)
    // sans que l'id soit encore remis a null. Sans ce garde-fou, un compte
    // dont la vue n'existe plus continuerait a accumuler des secondes.
    if (state.focusedId !== null && views.has(state.focusedId)) {
      state.tick(1)
    }
    chrome?.webContents.send('stats:tick', state.todaySeconds())
  }, 1000)

  setInterval(() => { void state.saveStats() }, 30_000)
})

app.on('before-quit', async event => {
  if (!state.statsDirty) return
  event.preventDefault()
  views.stopAll()
  try {
    await state.saveStats()
  } catch (error) {
    // Un echec d'ecriture (disque plein, permissions...) ne doit pas rendre
    // l'application infermable : on abandonne les stats en attente plutot que
    // de bloquer la fermeture. Journalise pour que le prochain lancement,
    // dont les totaux seront legerement en retard, ne soit pas un mystere.
    console.error('echec de l\'enregistrement des stats a la fermeture :', error)
  } finally {
    // Force a false meme apres un echec : sinon la prochaine passe de
    // before-quit reverrait statsDirty a true, rappellerait preventDefault(),
    // et on bouclerait indefiniment sur le meme echec d'ecriture.
    state.statsDirty = false
    app.quit()
  }
})

app.on('window-all-closed', () => app.quit())
