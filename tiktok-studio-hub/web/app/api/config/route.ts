import { NextResponse } from 'next/server'
import { getSettings } from '@/lib/config'

export async function GET () {
  const s = getSettings()
  return NextResponse.json({
    oauth_configured: s.oauthConfigured,
    demo_mode: false,
    redirect_uri: s.redirectUri
  })
}
