import { mkdir, readFile, writeFile } from 'fs/promises'
import path from 'path'
import { head } from '@vercel/blob'
import { SEED_ACCOUNTS } from './accounts'
import type {
  AccountStatus,
  AgentHeartbeat,
  DashboardPayload,
  Job,
  JobType,
  PendingFyp,
  StoreFile,
  WarmupEvent,
} from './types'

const BLOB_PATH = 'tiktok-warmup/state.json'
const LOCAL_PATH = path.join(process.cwd(), '.data', 'state.json')
const AGENT_STALE_MS = 20_000
const MAX_EVENTS = 200
const MAX_LOGS = 40

function emptyAccount (username: string): AccountStatus {
  const seed = SEED_ACCOUNTS.find(a => a.username === username)
  return {
    status: 'idle',
    ramp_up_day: 1,
    protocol_day: 1,
    role: seed?.role ?? 'flagship',
    protected: Boolean(seed?.protected),
    used_24h: { likes: 0, follows: 0, comments: 0 },
    caps_24h: { likes: [20, 30], follows: [10, 15], comments: [0, 3] },
    last_session: null,
    counters: { likes: 0, follows: 0, comments: 0, videos_watched: 0, scrolls: 0 },
    recent_logs: [],
  }
}

function emptyStore (): StoreFile {
  const accounts: Record<string, AccountStatus> = {}
  for (const acc of SEED_ACCOUNTS) {
    accounts[acc.username] = emptyAccount(acc.username)
  }
  return {
    agent: {
      lastSeenAt: null,
      iphone: false,
      wdaReady: false,
      wdaUrl: null,
      message: 'En attente du Mac',
    },
    accounts,
    jobs: [],
    nextJobId: 1,
    events: [],
    pendingFyp: [],
  }
}

export function storageMode (): 'blob' | 'local' {
  if (process.env.BLOB_READ_WRITE_TOKEN) return 'blob'
  if (!process.env.VERCEL) return 'local'
  throw new Error(
    'Stockage non configuré. Dans Vercel → tiktok-warmup → Storage → Create Database → Blob → Connect.'
  )
}

async function readBlobStore (): Promise<StoreFile> {
  try {
    const meta = await head(BLOB_PATH)
    const resp = await fetch(meta.url, { cache: 'no-store' })
    if (!resp.ok) return emptyStore()
    return hydrate(await resp.json())
  } catch {
    return emptyStore()
  }
}

async function writeBlobStore (data: StoreFile): Promise<void> {
  const { put } = await import('@vercel/blob')
  await put(BLOB_PATH, JSON.stringify(data), {
    access: 'public',
    addRandomSuffix: false,
    contentType: 'application/json',
  })
}

async function readLocalStore (): Promise<StoreFile> {
  try {
    const raw = await readFile(LOCAL_PATH, 'utf8')
    return hydrate(JSON.parse(raw))
  } catch {
    return emptyStore()
  }
}

async function writeLocalStore (data: StoreFile): Promise<void> {
  await mkdir(path.dirname(LOCAL_PATH), { recursive: true })
  await writeFile(LOCAL_PATH, JSON.stringify(data, null, 2), 'utf8')
}

function hydrate (raw: Partial<StoreFile>): StoreFile {
  const base = emptyStore()
  return {
    ...base,
    ...raw,
    agent: { ...base.agent, ...(raw.agent ?? {}) },
    accounts: { ...base.accounts, ...(raw.accounts ?? {}) },
    jobs: raw.jobs ?? [],
    nextJobId: raw.nextJobId ?? 1,
    events: raw.events ?? [],
    pendingFyp: raw.pendingFyp ?? [],
  }
}

async function readStore (): Promise<StoreFile> {
  return storageMode() === 'blob' ? readBlobStore() : readLocalStore()
}

async function writeStore (data: StoreFile): Promise<void> {
  if (storageMode() === 'blob') await writeBlobStore(data)
  else await writeLocalStore(data)
}

function agentOnline (agent: AgentHeartbeat): boolean {
  if (!agent.lastSeenAt) return false
  return Date.now() - Date.parse(agent.lastSeenAt) < AGENT_STALE_MS
}

export function buildDashboard (store: StoreFile): DashboardPayload {
  return {
    agent: store.agent,
    accounts: store.accounts,
    pendingFyp: store.pendingFyp,
    queued: store.jobs.filter(j => !j.claimedAt),
    agentOnline: agentOnline(store.agent),
  }
}

export async function getDashboard (): Promise<DashboardPayload> {
  return buildDashboard(await readStore())
}

export async function enqueueJob (partial: {
  type: JobType
  username?: string
  force?: boolean
  sessionId?: number
  count?: number
  day?: number
}): Promise<Job> {
  const store = await readStore()
  const job: Job = {
    id: store.nextJobId++,
    type: partial.type,
    username: partial.username,
    force: partial.force,
    sessionId: partial.sessionId,
    count: partial.count,
    day: partial.day,
    createdAt: new Date().toISOString(),
  }
  store.jobs.push(job)
  await writeStore(store)
  return job
}

export async function claimJobs (): Promise<Job[]> {
  const store = await readStore()
  const pending = store.jobs.filter(j => !j.claimedAt)
  if (pending.length === 0) return []
  const now = new Date().toISOString()
  for (const job of pending) job.claimedAt = now
  store.jobs = store.jobs.filter(j => {
    if (!j.claimedAt) return true
    return Date.now() - Date.parse(j.claimedAt) < 10 * 60_000
  })
  await writeStore(store)
  return pending
}

export async function applyHeartbeat (hb: Partial<AgentHeartbeat>): Promise<void> {
  const store = await readStore()
  store.agent = {
    ...store.agent,
    ...hb,
    lastSeenAt: new Date().toISOString(),
  }
  await writeStore(store)
}

export async function applySnapshot (payload: {
  accounts?: Record<string, AccountStatus>
  pendingFyp?: PendingFyp[]
  agent?: Partial<AgentHeartbeat>
}): Promise<void> {
  const store = await readStore()
  if (payload.accounts) {
    store.accounts = { ...store.accounts, ...payload.accounts }
  }
  if (payload.pendingFyp) store.pendingFyp = payload.pendingFyp
  if (payload.agent) {
    store.agent = {
      ...store.agent,
      ...payload.agent,
      lastSeenAt: new Date().toISOString(),
    }
  }
  await writeStore(store)
}

export async function applyEvents (events: WarmupEvent[]): Promise<void> {
  const store = await readStore()
  for (const event of events) {
    store.events.unshift(event)
    const username = event.username
    if (!username) continue
    const account = store.accounts[username] ?? emptyAccount(username)
    if (event.type === 'status' && event.data) {
      account.status = event.data
    }
    if (event.type === 'error' || event.type === 'error_event') {
      account.status = 'error'
    }
    if (event.type === 'action' || event.type === 'session' || event.type === 'refused') {
      const action = event.type === 'action'
        ? (event.data ?? '').split(': ')[0] || 'action'
        : event.type
      account.recent_logs = [
        {
          action,
          detail: event.data ?? '',
          time: event.timestamp,
        },
        ...account.recent_logs,
      ].slice(0, MAX_LOGS)
    }
    store.accounts[username] = account
  }
  store.events = store.events.slice(0, MAX_EVENTS)
  await writeStore(store)
}
