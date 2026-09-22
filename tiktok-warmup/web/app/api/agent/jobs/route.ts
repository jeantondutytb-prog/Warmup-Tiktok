import { claimJobs } from '@/lib/store'
import { isAgentAuthorized, unauthorized } from '@/lib/auth'

export async function POST (req: Request) {
  if (!isAgentAuthorized(req)) return unauthorized('agent')
  const jobs = await claimJobs()
  return Response.json({ jobs })
}
