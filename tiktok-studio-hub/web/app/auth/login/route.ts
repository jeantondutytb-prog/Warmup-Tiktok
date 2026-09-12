import { NextResponse } from 'next/server'
import { getSettings } from '@/lib/config'
import { saveOAuthState } from '@/lib/db'
import { newOAuthState } from '@/lib/pkce'
import { authorizeUrl } from '@/lib/tiktok'

export async function GET () {
  const settings = getSettings()
  if (!settings.oauthConfigured) {
    return NextResponse.json(
      { error: 'Configurez TIKTOK_CLIENT_KEY et TIKTOK_CLIENT_SECRET' },
      { status: 503 }
    )
  }

  const { state, codeVerifier, codeChallenge } = newOAuthState()
  try {
    await saveOAuthState(state, codeVerifier)
  } catch (e) {
    const message = e instanceof Error ? e.message : 'Erreur base de données'
    return NextResponse.json({ error: message }, { status: 503 })
  }

  const url = authorizeUrl(
    settings.clientKey,
    settings.redirectUri,
    state,
    settings.oauthScopes,
    codeChallenge
  )
  return NextResponse.redirect(url)
}
