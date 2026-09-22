import { enqueueJob } from '@/lib/store'
import { isDashboardAuthorized, unauthorized } from '@/lib/auth'

export async function POST (
  req: Request,
  { params }: { params: Promise<{ username: string }> }
) {
  if (!isDashboardAuthorized(req)) return unauthorized()
  const { username } = await params
  let body: { day?: unknown } = {}
  try {
    body = await req.json()
  } catch {
    return Response.json({ error: 'corps attendu : {"day": <entier>}' }, { status: 400 })
  }
  const day = Number(body.day)
  if (!Number.isInteger(day)) {
    return Response.json({ error: 'corps attendu : {"day": <entier>}' }, { status: 400 })
  }
  const job = await enqueueJob({ type: 'protocol-day', username, day })
  return Response.json({ ok: true, job })
}
