import { NextResponse } from 'next/server'
import { getSettings } from '@/lib/config'
import { createOAuthCookieValue, OAUTH_COOKIE } from '@/lib/oauth-cookie'
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
  const url = authorizeUrl(
    settings.clientKey,
    settings.redirectUri,
    state,
    settings.oauthScopes,
    codeChallenge
  )

  const response = NextResponse.redirect(url)
  response.cookies.set(
    OAUTH_COOKIE,
    createOAuthCookieValue(state, codeVerifier, settings.clientSecret),
    {
      httpOnly: true,
      secure: process.env.NODE_ENV === 'production',
      sameSite: 'lax',
      maxAge: 600,
      path: '/'
    }
  )
  return response
}
