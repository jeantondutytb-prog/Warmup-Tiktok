const TOKEN_URL = 'https://open.tiktokapis.com/v2/oauth/token/'
const USER_INFO_URL = 'https://open.tiktokapis.com/v2/user/info/'
const VIDEO_LIST_URL = 'https://open.tiktokapis.com/v2/video/list/'
const AUTH_URL = 'https://www.tiktok.com/v2/auth/authorize/'

const USER_FIELDS =
  'open_id,union_id,avatar_url,display_name,follower_count,following_count,likes_count,video_count'
const VIDEO_FIELDS =
  'id,title,cover_image_url,create_time,view_count,like_count,comment_count,share_count'

export class TikTokApiError extends Error {
  statusCode?: number
  constructor (message: string, statusCode?: number) {
    super(message)
    this.statusCode = statusCode
  }
}

function parseTokenResponse (payload: Record<string, unknown>): Record<string, unknown> {
  const err = (payload.error ?? {}) as Record<string, unknown>
  if (typeof err === 'string') throw new TikTokApiError(err)
  if (err.code && err.code !== 'ok') {
    throw new TikTokApiError(String(err.message ?? err.code))
  }
  const data = (payload.data ?? payload) as Record<string, unknown>
  if (!data.access_token) throw new TikTokApiError('Réponse OAuth sans access_token')
  return data
}

function parseDataResponse (payload: Record<string, unknown>): Record<string, unknown> {
  const err = (payload.error ?? {}) as Record<string, unknown>
  if (err.code && err.code !== 'ok') {
    throw new TikTokApiError(String(err.message ?? err.code))
  }
  return (payload.data ?? {}) as Record<string, unknown>
}

export function authorizeUrl (
  clientKey: string,
  redirectUri: string,
  state: string,
  scope: string,
  codeChallenge: string
): string {
  const params = new URLSearchParams({
    client_key: clientKey,
    scope,
    response_type: 'code',
    redirect_uri: redirectUri,
    state,
    code_challenge: codeChallenge,
    code_challenge_method: 'S256'
  })
  return `${AUTH_URL}?${params.toString()}`
}

export async function exchangeCode (
  clientKey: string,
  clientSecret: string,
  code: string,
  redirectUri: string,
  codeVerifier: string
): Promise<Record<string, unknown>> {
  const body = new URLSearchParams({
    client_key: clientKey,
    client_secret: clientSecret,
    code,
    grant_type: 'authorization_code',
    redirect_uri: redirectUri,
    code_verifier: codeVerifier
  })
  const resp = await fetch(TOKEN_URL, {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body
  })
  if (!resp.ok) throw new TikTokApiError(await resp.text(), resp.status)
  return parseTokenResponse(await resp.json())
}

export async function fetchUserInfo (accessToken: string): Promise<Record<string, unknown>> {
  const url = `${USER_INFO_URL}?fields=${USER_FIELDS}`
  const resp = await fetch(url, {
    headers: { Authorization: `Bearer ${accessToken}` }
  })
  if (!resp.ok) throw new TikTokApiError(await resp.text(), resp.status)
  return parseDataResponse(await resp.json())
}

export async function fetchAllVideos (accessToken: string): Promise<Record<string, unknown>[]> {
  const videos: Record<string, unknown>[] = []
  let cursor: number | undefined

  while (true) {
    const body: Record<string, unknown> = { max_count: 20 }
    if (cursor !== undefined) body.cursor = cursor

    const resp = await fetch(`${VIDEO_LIST_URL}?fields=${VIDEO_FIELDS}`, {
      method: 'POST',
      headers: {
        Authorization: `Bearer ${accessToken}`,
        'Content-Type': 'application/json'
      },
      body: JSON.stringify(body)
    })
    if (!resp.ok) throw new TikTokApiError(await resp.text(), resp.status)
    const data = parseDataResponse(await resp.json())
    videos.push(...((data.videos as Record<string, unknown>[]) ?? []))
    if (!data.has_more) break
    cursor = data.cursor as number | undefined
    if (cursor === undefined) break
  }
  return videos
}

export function sumVideos (videos: Record<string, unknown>[]) {
  return {
    views: videos.reduce((n, v) => n + Number(v.view_count ?? 0), 0),
    likes: videos.reduce((n, v) => n + Number(v.like_count ?? 0), 0),
    comments: videos.reduce((n, v) => n + Number(v.comment_count ?? 0), 0),
    shares: videos.reduce((n, v) => n + Number(v.share_count ?? 0), 0)
  }
}
