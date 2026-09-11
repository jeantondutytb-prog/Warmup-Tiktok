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

/** Ratio largeur/hauteur d'un telephone en portrait, pour computeLayout. */
export const PORTRAIT_ASPECT = 9 / 16

export type ViewStatus = 'stopped' | 'loading' | 'ready' | 'error'
