import { ipcMain, app } from 'electron'
import { randomUUID } from 'node:crypto'
import { join } from 'node:path'
import { readJson, writeJsonAtomic } from './storage'
import { ViewManager } from './view-manager'
import {
  emptyAccounts, createAccount, updateAccount, deleteAccount, migrate
} from '../core/accounts'
import { emptyStats, addSeconds, dayKey, purgeOlderThan, migrateStats } from '../core/stats'
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
    // migrateStats ne leve jamais : un fichier corrompu ou d'un schema
    // different retombe sur un fichier vide plutot que de faire echouer le
    // demarrage (cf. purgeOlderThan qui, lui, suppose une forme deja valide).
    this.stats = migrateStats(await readJson<unknown>(this.statsPath, null))
    const cutoff = new Date()
    cutoff.setDate(cutoff.getDate() - RETENTION_DAYS)
    this.stats = purgeOlderThan(this.stats, dayKey(cutoff))
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
    try {
      await views.destroy(account)
    } catch (error) {
      // views.destroy() demonte deja la vue de facon synchrone avant d'attendre
      // l'effacement de la session : si cet effacement echoue (disque,
      // permissions...), la vue est deja partie mais le compte ne doit pas
      // rester zombie dans la liste pour autant. On journalise et on continue
      // la suppression ; seul le stockage de la session peut avoir survecu.
      console.error(`echec de l'effacement de la session pour le compte ${id} :`, error)
    }
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

  ipcMain.handle('view:focus', (_event, id: string) => {
    views.focus(id)
  })

  ipcMain.handle('layout:apply', (_event, cells: CellRect[], focusedId: string | null) => {
    state.focusedId = focusedId
    views.applyLayout(cells, focusedId)
  })

  ipcMain.handle('stats:today', () => state.todaySeconds())

  // Le pilote de session (src/core/pilot.ts) a besoin de l'historique complet
  // (fenetre glissante de WINDOW_DAYS jours, derniere session active) pour
  // calculer regularityScore/daysSinceLastSession : stats:today, qui ne
  // renvoie que le jour courant, ne suffit pas. Meme forme que les autres
  // canaux : aucun parametre, l'etat courant en retour.
  ipcMain.handle('stats:full', () => state.stats)
}
