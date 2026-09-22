import { applyEvents } from '@/lib/store'
import { isAgentAuthorized, unauthorized } from '@/lib/auth'
import type { WarmupEvent } from '@/lib/types'

export async function POST (req: Request) {
  if (!isAgentAuthorized(req)) return unauthorized('agent')
  let body: { events?: WarmupEvent[] } = {}
  try {
    body = await req.json()
  } catch {
    return Response.json({ error: 'JSON attendu' }, { status: 400 })
  }
  const events = Array.isArray(body.events) ? body.events : []
  await applyEvents(events)
  return Response.json({ ok: true, accepted: events.length })
}
