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
  const seenIds = new Set<string>()
  for (const entry of candidate.accounts) {
    if (typeof entry !== 'object' || entry === null) continue
    const partial = entry as Partial<Account>
    if (typeof partial.id !== 'string' || partial.id === '') continue
    if (seenIds.has(partial.id)) continue
    seenIds.add(partial.id)

    // Validate proxy: only accept if it's an object with a string server property
    let validProxy: Account['proxy'] = null
    if (typeof partial.proxy === 'object' && partial.proxy !== null) {
      const proxyObj = partial.proxy as unknown as Record<string, unknown>
      if (typeof proxyObj.server === 'string') {
        validProxy = {
          server: proxyObj.server,
          ...(typeof proxyObj.username === 'string' && { username: proxyObj.username }),
          ...(typeof proxyObj.password === 'string' && { password: proxyObj.password })
        } as Account['proxy']
      }
    }

    accounts.push({
      id: partial.id,
      label: typeof partial.label === 'string' ? partial.label : partial.id,
      partition: partitionFor(partial.id),
      proxy: validProxy,
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
