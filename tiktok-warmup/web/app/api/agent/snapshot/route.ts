import { applySnapshot } from '@/lib/store'
import { isAgentAuthorized, unauthorized } from '@/lib/auth'
import type { AccountStatus, PendingFyp } from '@/lib/types'

export async function POST (req: Request) {
  if (!isAgentAuthorized(req)) return unauthorized('agent')
  let body: {
    accounts?: Record<string, AccountStatus>
    pendingFyp?: PendingFyp[]
    agent?: { iphone?: boolean; wdaReady?: boolean; wdaUrl?: string | null; message?: string }
  } = {}
  try {
    body = await req.json()
  } catch {
    return Response.json({ error: 'JSON attendu' }, { status: 400 })
  }
  await applySnapshot(body)
  return Response.json({ ok: true })
}
