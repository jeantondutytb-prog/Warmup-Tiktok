import { NextResponse } from 'next/server'
import { buildDashboard, listAccounts } from '@/lib/store'

export const dynamic = 'force-dynamic'

export async function GET () {
  try {
    const rows = await listAccounts()
    return NextResponse.json(buildDashboard(rows))
  } catch (e) {
    const message = e instanceof Error ? e.message : 'Erreur stockage'
    return NextResponse.json({ error: message }, { status: 503 })
  }
}
