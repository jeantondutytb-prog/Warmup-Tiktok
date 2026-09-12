import crypto from 'crypto'

const VERIFIER_CHARS =
  'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._~'

export function generateCodeVerifier (length = 64): string {
  let result = ''
  for (let i = 0; i < length; i++) {
    result += VERIFIER_CHARS[crypto.randomInt(0, VERIFIER_CHARS.length)]
  }
  return result
}

/** TikTok Desktop PKCE : HEX(SHA256(verifier)), pas base64url. */
export function generateCodeChallenge (codeVerifier: string): string {
  return crypto.createHash('sha256').update(codeVerifier, 'utf8').digest('hex')
}

export function newOAuthState (): { state: string; codeVerifier: string; codeChallenge: string } {
  const state = crypto.randomBytes(24).toString('base64url')
  const codeVerifier = generateCodeVerifier()
  const codeChallenge = generateCodeChallenge(codeVerifier)
  return { state, codeVerifier, codeChallenge }
}
