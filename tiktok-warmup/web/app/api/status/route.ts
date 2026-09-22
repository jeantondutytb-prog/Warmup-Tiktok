import { getDashboard } from '@/lib/store'
import { isDashboardAuthorized, unauthorized } from '@/lib/auth'

export const dynamic = 'force-dynamic'

export async function GET (req: Request) {
  if (!isDashboardAuthorized(req)) return unauthorized()
  try {
    return Response.json(await getDashboard())
  } catch (err) {
    console.error('status', err)
    return Response.json({ error: 'lecture du store impossible' }, { status: 500 })
  }
}
