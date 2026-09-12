import { sql } from '@vercel/postgres'

let schemaReady = false

export async function ensureSchema (): Promise<void> {
  if (schemaReady) return
  await sql`
    CREATE TABLE IF NOT EXISTS connected_accounts (
      id SERIAL PRIMARY KEY,
      open_id TEXT NOT NULL UNIQUE,
      display_name TEXT NOT NULL DEFAULT '',
      avatar_url TEXT NOT NULL DEFAULT '',
      access_token TEXT NOT NULL DEFAULT '',
      refresh_token TEXT NOT NULL DEFAULT '',
      token_expires_at TIMESTAMPTZ,
      refresh_expires_at TIMESTAMPTZ,
      follower_count INTEGER NOT NULL DEFAULT 0,
      following_count INTEGER NOT NULL DEFAULT 0,
      likes_count INTEGER NOT NULL DEFAULT 0,
      video_count INTEGER NOT NULL DEFAULT 0,
      total_views INTEGER NOT NULL DEFAULT 0,
      total_video_likes INTEGER NOT NULL DEFAULT 0,
      total_comments INTEGER NOT NULL DEFAULT 0,
      total_shares INTEGER NOT NULL DEFAULT 0,
      last_synced_at TIMESTAMPTZ,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
  `
  await sql`
    CREATE TABLE IF NOT EXISTS oauth_states (
      state TEXT PRIMARY KEY,
      code_verifier TEXT NOT NULL,
      created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
    )
  `
  schemaReady = true
}

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

export async function saveOAuthState (state: string, codeVerifier: string): Promise<void> {
  await ensureSchema()
  await sql`INSERT INTO oauth_states (state, code_verifier) VALUES (${state}, ${codeVerifier})`
}

export async function consumeOAuthState (state: string): Promise<string | null> {
  await ensureSchema()
  const result = await sql`
    DELETE FROM oauth_states
    WHERE state = ${state}
      AND created_at > NOW() - INTERVAL '10 minutes'
    RETURNING code_verifier
  `
  return result.rows[0]?.code_verifier ?? null
}

export async function listAccounts (): Promise<AccountRow[]> {
  await ensureSchema()
  const result = await sql`
    SELECT id, open_id, display_name, avatar_url, access_token, refresh_token,
           follower_count, following_count, likes_count, video_count,
           total_views, total_video_likes, total_comments, total_shares,
           last_synced_at::text
    FROM connected_accounts
    ORDER BY display_name
  `
  return result.rows as AccountRow[]
}

export async function deleteAccount (id: number): Promise<void> {
  await ensureSchema()
  await sql`DELETE FROM connected_accounts WHERE id = ${id}`
}

export async function getAccount (id: number): Promise<AccountRow | null> {
  await ensureSchema()
  const result = await sql`
    SELECT id, open_id, display_name, avatar_url, access_token, refresh_token,
           follower_count, following_count, likes_count, video_count,
           total_views, total_video_likes, total_comments, total_shares,
           last_synced_at::text
    FROM connected_accounts WHERE id = ${id}
  `
  return (result.rows[0] as AccountRow) ?? null
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
  await ensureSchema()
  await sql`
    INSERT INTO connected_accounts (
      open_id, display_name, avatar_url, access_token, refresh_token,
      follower_count, following_count, likes_count, video_count,
      total_views, total_video_likes, total_comments, total_shares, last_synced_at
    ) VALUES (
      ${data.openId}, ${data.displayName}, ${data.avatarUrl},
      ${data.accessToken}, ${data.refreshToken},
      ${data.followerCount}, ${data.followingCount}, ${data.likesCount}, ${data.videoCount},
      ${data.totalViews}, ${data.totalVideoLikes}, ${data.totalComments}, ${data.totalShares}, NOW()
    )
    ON CONFLICT (open_id) DO UPDATE SET
      display_name = EXCLUDED.display_name,
      avatar_url = EXCLUDED.avatar_url,
      access_token = EXCLUDED.access_token,
      refresh_token = EXCLUDED.refresh_token,
      follower_count = EXCLUDED.follower_count,
      following_count = EXCLUDED.following_count,
      likes_count = EXCLUDED.likes_count,
      video_count = EXCLUDED.video_count,
      total_views = EXCLUDED.total_views,
      total_video_likes = EXCLUDED.total_video_likes,
      total_comments = EXCLUDED.total_comments,
      total_shares = EXCLUDED.total_shares,
      last_synced_at = NOW()
  `
}

export async function updateAccountStats (
  id: number,
  data: Omit<Parameters<typeof upsertAccount>[0], 'openId' | 'accessToken' | 'refreshToken'> & {
    accessToken: string
    refreshToken: string
  }
): Promise<void> {
  await ensureSchema()
  await sql`
    UPDATE connected_accounts SET
      display_name = ${data.displayName},
      avatar_url = ${data.avatarUrl},
      access_token = ${data.accessToken},
      refresh_token = ${data.refreshToken},
      follower_count = ${data.followerCount},
      following_count = ${data.followingCount},
      likes_count = ${data.likesCount},
      video_count = ${data.videoCount},
      total_views = ${data.totalViews},
      total_video_likes = ${data.totalVideoLikes},
      total_comments = ${data.totalComments},
      total_shares = ${data.totalShares},
      last_synced_at = NOW()
    WHERE id = ${id}
  `
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
    is_demo: row.access_token === 'demo'
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
