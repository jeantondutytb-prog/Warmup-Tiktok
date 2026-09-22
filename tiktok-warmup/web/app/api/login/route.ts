import { loginCookie, passwordMatches } from '@/lib/auth'

export async function POST (req: Request) {
  let body: { password?: string } = {}
  try {
    body = await req.json()
  } catch {
    return Response.json({ error: 'corps JSON attendu' }, { status: 400 })
  }
  if (!passwordMatches(body.password ?? '')) {
    return Response.json({ error: 'mot de passe incorrect' }, { status: 401 })
  }
  return Response.json({ ok: true }, { headers: { 'Set-Cookie': loginCookie() } })
}
