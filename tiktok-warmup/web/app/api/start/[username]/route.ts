import { enqueueJob } from '@/lib/store'
import { isDashboardAuthorized, unauthorized } from '@/lib/auth'

export async function POST (
  req: Request,
  { params }: { params: Promise<{ username: string }> }
) {
  if (!isDashboardAuthorized(req)) return unauthorized()
  const { username } = await params
  const url = new URL(req.url)
  const force = url.searchParams.get('force') === '1'
  const job = await enqueueJob({ type: 'start', username, force })
  return Response.json({ ok: true, forced: force, job })
}
