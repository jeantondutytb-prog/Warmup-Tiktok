import { NextResponse } from 'next/server'
import { deleteAccount } from '@/lib/store'

export const dynamic = 'force-dynamic'

export async function DELETE (
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  try {
    const { id } = await params
    await deleteAccount(Number(id))
    return NextResponse.json({ ok: true })
  } catch (e) {
    const message = e instanceof Error ? e.message : 'Erreur stockage'
    return NextResponse.json({ error: message }, { status: 503 })
  }
}
