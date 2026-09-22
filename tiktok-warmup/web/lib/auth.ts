import { createHash, timingSafeEqual } from 'crypto'

const COOKIE = 'warmup_auth'

function expectedCookie (): string {
  const password = process.env.DASHBOARD_PASSWORD ?? ''
  return createHash('sha256').update(`warmup:${password}`).digest('hex')
}

export function dashboardPasswordRequired (): boolean {
  return Boolean(process.env.DASHBOARD_PASSWORD)
}

export function isDashboardAuthorized (req: Request): boolean {
  if (!dashboardPasswordRequired()) return true
  const cookie = req.headers.get('cookie') ?? ''
  const match = cookie.match(new RegExp(`(?:^|;\\s*)${COOKIE}=([^;]+)`))
  if (!match) return false
  const got = Buffer.from(match[1])
  const exp = Buffer.from(expectedCookie())
  if (got.length !== exp.length) return false
  return timingSafeEqual(got, exp)
}

export function passwordMatches (password: string): boolean {
  const expected = process.env.DASHBOARD_PASSWORD ?? ''
  if (!expected) return true
  const a = Buffer.from(password)
  const b = Buffer.from(expected)
  if (a.length !== b.length) return false
  return timingSafeEqual(a, b)
}

export function loginCookie (): string {
  const secure = process.env.VERCEL ? '; Secure' : ''
  return `${COOKIE}=${expectedCookie()}; Path=/; HttpOnly; SameSite=Lax${secure}; Max-Age=2592000`
}

export function logoutCookie (): string {
  return `${COOKIE}=; Path=/; HttpOnly; SameSite=Lax; Max-Age=0`
}

export function isAgentAuthorized (req: Request): boolean {
  const token = process.env.AGENT_TOKEN
  if (!token) return false
  const auth = req.headers.get('authorization') ?? ''
  const got = Buffer.from(auth)
  const exp = Buffer.from(`Bearer ${token}`)
  if (got.length !== exp.length) return false
  return timingSafeEqual(got, exp)
}

export function unauthorized (kind: 'dashboard' | 'agent' = 'dashboard'): Response {
  return Response.json(
    { error: kind === 'agent' ? 'agent token invalide' : 'non autorisé' },
    { status: 401 }
  )
}
