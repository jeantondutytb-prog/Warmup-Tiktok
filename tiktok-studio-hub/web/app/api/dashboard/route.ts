import { NextResponse } from 'next/server'
import { buildDashboard, listAccounts } from '@/lib/db'

export async function GET () {
  try {
    const rows = await listAccounts()
    return NextResponse.json(buildDashboard(rows))
  } catch (e) {
    const message = e instanceof Error ? e.message : 'Erreur base de données'
    return NextResponse.json({ error: message }, { status: 503 })
  }
}
