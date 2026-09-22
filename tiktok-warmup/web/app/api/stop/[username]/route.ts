import { enqueueJob } from '@/lib/store'
import { isDashboardAuthorized, unauthorized } from '@/lib/auth'

export async function POST (
  req: Request,
  { params }: { params: Promise<{ username: string }> }
) {
  if (!isDashboardAuthorized(req)) return unauthorized()
  const { username } = await params
  const job = await enqueueJob({ type: 'stop-all', username })
  return Response.json({ ok: true, job })
}
