import { getDashboard } from '@/lib/store'
import { isDashboardAuthorized, unauthorized } from '@/lib/auth'

export const dynamic = 'force-dynamic'

export async function GET (req: Request) {
  if (!isDashboardAuthorized(req)) return unauthorized()
  const dash = await getDashboard()
  return Response.json(dash.pendingFyp)
}
