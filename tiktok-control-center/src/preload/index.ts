import { contextBridge, ipcRenderer } from 'electron'
import type { Account, CellRect, StatsFile } from '../core/types'
import type { StatusEvent } from '../main/view-manager'

export interface Api {
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

const api: Api = {
  listAccounts: () => ipcRenderer.invoke('accounts:list'),
  createAccount: (label) => ipcRenderer.invoke('accounts:create', label),
  updateAccount: (id, patch) => ipcRenderer.invoke('accounts:update', id, patch),
  deleteAccount: (id) => ipcRenderer.invoke('accounts:delete', id),
  startView: (id) => ipcRenderer.invoke('view:start', id),
  stopView: (id) => ipcRenderer.invoke('view:stop', id),
  reloadView: (id) => ipcRenderer.invoke('view:reload', id),
  focusView: (id) => ipcRenderer.invoke('view:focus', id),
  applyLayout: (cells, focusedId) => ipcRenderer.invoke('layout:apply', cells, focusedId),
  getStats: () => ipcRenderer.invoke('stats:today'),
  getFullStats: () => ipcRenderer.invoke('stats:full'),
  onStatus: (handler) => { ipcRenderer.on('view:state', (_e, payload) => handler(payload)) },
  onStats: (handler) => { ipcRenderer.on('stats:tick', (_e, payload) => handler(payload)) }
}

contextBridge.exposeInMainWorld('api', api)
