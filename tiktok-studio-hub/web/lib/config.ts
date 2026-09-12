export function getSettings () {
  const clientKey = (process.env.TIKTOK_CLIENT_KEY ?? '').trim()
  const clientSecret = (process.env.TIKTOK_CLIENT_SECRET ?? '').trim()
  const placeholders = new Set(['', 'your_client_key', 'your_client_secret', 'changeme'])

  const appBase = (
    process.env.APP_BASE_URL ??
    process.env.VERCEL_PROJECT_PRODUCTION_URL ??
    (process.env.VERCEL_URL ? `https://${process.env.VERCEL_URL}` : 'http://127.0.0.1:8080')
  ).replace(/\/$/, '')

  const redirectUri = (process.env.TIKTOK_REDIRECT_URI ?? `${appBase}/auth/callback`).trim()

  return {
    clientKey: placeholders.has(clientKey) ? '' : clientKey,
    clientSecret: placeholders.has(clientSecret) ? '' : clientSecret,
    redirectUri,
    appBaseUrl: appBase,
    oauthConfigured: !placeholders.has(clientKey) && !placeholders.has(clientSecret),
    oauthScopes: 'user.info.basic,user.info.stats,video.list'
  }
}
