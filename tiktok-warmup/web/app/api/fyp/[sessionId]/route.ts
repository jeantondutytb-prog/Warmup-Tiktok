import { enqueueJob } from '@/lib/store'
import { isDashboardAuthorized, unauthorized } from '@/lib/auth'

export async function POST (
  req: Request,
  { params }: { params: Promise<{ sessionId: string }> }
) {
  if (!isDashboardAuthorized(req)) return unauthorized()
  const { sessionId } = await params
  let body: { count?: unknown } = {}
  try {
    body = await req.json()
  } catch {
    return Response.json({ error: 'corps attendu : {"count": <entier>}' }, { status: 400 })
  }
  const count = Number(body.count)
  if (!Number.isInteger(count)) {
    return Response.json({ error: 'corps attendu : {"count": <entier>}' }, { status: 400 })
  }
  const job = await enqueueJob({ type: 'fyp', sessionId: Number(sessionId), count })
  return Response.json({ ok: true, job })
}
