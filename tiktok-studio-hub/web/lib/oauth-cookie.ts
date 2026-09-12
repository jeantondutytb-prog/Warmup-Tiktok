import crypto from 'crypto'

interface OAuthPayload {
  state: string
  codeVerifier: string
  exp: number
}

export function createOAuthCookieValue (
  state: string,
  codeVerifier: string,
  secret: string
): string {
  const payload: OAuthPayload = {
    state,
    codeVerifier,
    exp: Date.now() + 10 * 60 * 1000
  }
  const data = Buffer.from(JSON.stringify(payload)).toString('base64url')
  const sig = crypto.createHmac('sha256', secret).update(data).digest('base64url')
  return `${data}.${sig}`
}

export function readOAuthCookieValue (
  token: string,
  secret: string,
  expectedState: string
): string | null {
  const dot = token.indexOf('.')
  if (dot < 0) return null
  const data = token.slice(0, dot)
  const sig = token.slice(dot + 1)
  const expectedSig = crypto.createHmac('sha256', secret).update(data).digest('base64url')
  if (sig !== expectedSig) return null

  let payload: OAuthPayload
  try {
    payload = JSON.parse(Buffer.from(data, 'base64url').toString('utf8'))
  } catch {
    return null
  }
  if (payload.state !== expectedState) return null
  if (payload.exp < Date.now()) return null
  return payload.codeVerifier
}

export const OAUTH_COOKIE = 'tt_oauth'
