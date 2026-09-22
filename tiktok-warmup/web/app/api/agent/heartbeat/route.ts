import { applyHeartbeat } from '@/lib/store'
import { isAgentAuthorized, unauthorized } from '@/lib/auth'

export async function POST (req: Request) {
  if (!isAgentAuthorized(req)) return unauthorized('agent')
  let body: Record<string, unknown> = {}
  try {
    body = await req.json()
  } catch {
    return Response.json({ error: 'JSON attendu' }, { status: 400 })
  }
  await applyHeartbeat({
    iphone: Boolean(body.iphone),
    wdaReady: Boolean(body.wdaReady),
    wdaUrl: typeof body.wdaUrl === 'string' ? body.wdaUrl : null,
    message: typeof body.message === 'string' ? body.message : '',
    warmupRunning: Boolean(body.warmupRunning),
  })
  return Response.json({ ok: true })
}
