import { enqueueJob } from '@/lib/store'
import { isDashboardAuthorized, unauthorized } from '@/lib/auth'

export async function POST (req: Request) {
  if (!isDashboardAuthorized(req)) return unauthorized()
  const job = await enqueueJob({ type: 'stop-all' })
  return Response.json({ ok: true, job })
}
