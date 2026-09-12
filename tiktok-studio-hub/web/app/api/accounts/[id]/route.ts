import { NextResponse } from 'next/server'
import { deleteAccount } from '@/lib/db'

export async function DELETE (
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  await deleteAccount(Number(id))
  return NextResponse.json({ ok: true })
}
