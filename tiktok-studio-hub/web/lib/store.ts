import { mkdir, readFile, writeFile } from 'fs/promises'
import path from 'path'
import { head } from '@vercel/blob'

const BLOB_PATH = 'tiktok-studio/accounts.json'
const LOCAL_PATH = path.join(process.cwd(), '.data', 'accounts.json')

export interface AccountRow {
  id: number
  open_id: string
  display_name: string
  avatar_url: string
  access_token: string
  refresh_token: string
  follower_count: number
  following_count: number
  likes_count: number
  video_count: number
  total_views: number
  total_video_likes: number
  total_comments: number
  total_shares: number
  last_synced_at: string | null
}

interface StoreFile {
  nextId: number
  accounts: AccountRow[]
}

function emptyStore (): StoreFile {
  return { nextId: 1, accounts: [] }
}

function storageMode (): 'blob' | 'local' {
  if (process.env.BLOB_READ_WRITE_TOKEN) return 'blob'
  if (!process.env.VERCEL) return 'local'
  throw new Error(
    'Stockage non configuré. Dans Vercel → tiktok-studio-hub → Storage → Create Database → Blob → Connect.'
  )
}

async function readBlobStore (): Promise<StoreFile> {
  try {
    const meta = await head(BLOB_PATH)
    const resp = await fetch(meta.url)
    if (!resp.ok) return emptyStore()
    return (await resp.json()) as StoreFile
  } catch {
    return emptyStore()
  }
}

async function writeBlobStore (data: StoreFile): Promise<void> {
  const { put } = await import('@vercel/blob')
  await put(BLOB_PATH, JSON.stringify(data), {
    access: 'public',
    addRandomSuffix: false,
    contentType: 'application/json'
  })
}

async function readLocalStore (): Promise<StoreFile> {
  try {
    const raw = await readFile(LOCAL_PATH, 'utf8')
    return JSON.parse(raw) as StoreFile
  } catch {
    return emptyStore()
  }
}

async function writeLocalStore (data: StoreFile): Promise<void> {
  await mkdir(path.dirname(LOCAL_PATH), { recursive: true })
  await writeFile(LOCAL_PATH, JSON.stringify(data, null, 2), 'utf8')
}

async function readStore (): Promise<StoreFile> {
  return storageMode() === 'blob' ? readBlobStore() : readLocalStore()
}

async function writeStore (data: StoreFile): Promise<void> {
  if (storageMode() === 'blob') await writeBlobStore(data)
  else await writeLocalStore(data)
}

export async function listAccounts (): Promise<AccountRow[]> {
  const store = await readStore()
  return [...store.accounts].sort((a, b) => a.display_name.localeCompare(b.display_name))
}

export async function getAccount (id: number): Promise<AccountRow | null> {
  const store = await readStore()
  return store.accounts.find(a => a.id === id) ?? null
}

export async function deleteAccount (id: number): Promise<void> {
  const store = await readStore()
  store.accounts = store.accounts.filter(a => a.id !== id)
  await writeStore(store)
}

export async function upsertAccount (data: {
  openId: string
  displayName: string
  avatarUrl: string
  accessToken: string
  refreshToken: string
  followerCount: number
  followingCount: number
  likesCount: number
  videoCount: number
  totalViews: number
  totalVideoLikes: number
  totalComments: number
  totalShares: number
}): Promise<void> {
  const store = await readStore()
  const existing = store.accounts.find(a => a.open_id === data.openId)
  const now = new Date().toISOString()
  const row: AccountRow = {
    id: existing?.id ?? store.nextId++,
    open_id: data.openId,
    display_name: data.displayName,
    avatar_url: data.avatarUrl,
    access_token: data.accessToken,
    refresh_token: data.refreshToken,
    follower_count: data.followerCount,
    following_count: data.followingCount,
    likes_count: data.likesCount,
    video_count: data.videoCount,
    total_views: data.totalViews,
    total_video_likes: data.totalVideoLikes,
    total_comments: data.totalComments,
    total_shares: data.totalShares,
    last_synced_at: now
  }
  if (existing) {
    store.accounts = store.accounts.map(a => (a.open_id === data.openId ? row : a))
  } else {
    store.accounts.push(row)
  }
  await writeStore(store)
}

export async function updateAccountStats (
  id: number,
  data: Omit<Parameters<typeof upsertAccount>[0], 'openId'> & { accessToken: string; refreshToken: string }
): Promise<void> {
  const store = await readStore()
  const idx = store.accounts.findIndex(a => a.id === id)
  if (idx < 0) return
  const prev = store.accounts[idx]
  store.accounts[idx] = {
    ...prev,
    display_name: data.displayName,
    avatar_url: data.avatarUrl,
    access_token: data.accessToken,
    refresh_token: data.refreshToken,
    follower_count: data.followerCount,
    following_count: data.followingCount,
    likes_count: data.likesCount,
    video_count: data.videoCount,
    total_views: data.totalViews,
    total_video_likes: data.totalVideoLikes,
    total_comments: data.totalComments,
    total_shares: data.totalShares,
    last_synced_at: new Date().toISOString()
  }
  await writeStore(store)
}

export function accountToJson (row: AccountRow) {
  return {
    id: row.id,
    open_id: row.open_id,
    display_name: row.display_name,
    avatar_url: row.avatar_url,
    follower_count: row.follower_count,
    following_count: row.following_count,
    likes_count: row.likes_count,
    video_count: row.video_count,
    total_views: row.total_views,
    total_video_likes: row.total_video_likes,
    total_comments: row.total_comments,
    total_shares: row.total_shares,
    last_synced_at: row.last_synced_at,
    is_demo: false
  }
}

export function buildDashboard (rows: AccountRow[]) {
  const accounts = rows.map(accountToJson)
  return {
    totals: {
      accounts: accounts.length,
      followers: accounts.reduce((n, a) => n + a.follower_count, 0),
      following: accounts.reduce((n, a) => n + a.following_count, 0),
      profile_likes: accounts.reduce((n, a) => n + a.likes_count, 0),
      videos: accounts.reduce((n, a) => n + a.video_count, 0),
      views: accounts.reduce((n, a) => n + a.total_views, 0),
      likes: accounts.reduce((n, a) => n + a.total_video_likes, 0),
      comments: accounts.reduce((n, a) => n + a.total_comments, 0),
      shares: accounts.reduce((n, a) => n + a.total_shares, 0)
    },
    accounts
  }
}
