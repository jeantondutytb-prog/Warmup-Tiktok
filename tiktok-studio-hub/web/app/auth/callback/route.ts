import { NextRequest, NextResponse } from 'next/server'
import { getSettings } from '@/lib/config'
import { OAUTH_COOKIE, readOAuthCookieValue } from '@/lib/oauth-cookie'
import { upsertAccount } from '@/lib/store'
import {
  exchangeCode,
  fetchAllVideos,
  fetchUserInfo,
  sumVideos,
  TikTokApiError
} from '@/lib/tiktok'

export async function GET (request: NextRequest) {
  const settings = getSettings()
  const params = request.nextUrl.searchParams
  const error = params.get('error')
  const code = params.get('code') ?? ''
  const state = params.get('state') ?? ''

  const redirect = (query: string) =>
    NextResponse.redirect(new URL(`/${query}`, settings.appBaseUrl))

  if (error) {
    return redirect(`?auth_error=${encodeURIComponent(error)}`)
  }
  if (!code) {
    return redirect('?auth_error=missing_code')
  }

  const cookie = request.cookies.get(OAUTH_COOKIE)?.value
  const codeVerifier = cookie
    ? readOAuthCookieValue(cookie, settings.clientSecret, state)
    : null
  if (!codeVerifier) {
    return redirect('?auth_error=invalid_state')
  }

  try {
    const tokenData = await exchangeCode(
      settings.clientKey,
      settings.clientSecret,
      code,
      settings.redirectUri,
      codeVerifier
    )
    const accessToken = String(tokenData.access_token)
    const user = await fetchUserInfo(accessToken)
    const videos = await fetchAllVideos(accessToken)
    const totals = sumVideos(videos)

    await upsertAccount({
      openId: String(user.open_id ?? tokenData.open_id),
      displayName: String(user.display_name ?? ''),
      avatarUrl: String(user.avatar_url ?? ''),
      accessToken,
      refreshToken: String(tokenData.refresh_token ?? ''),
      followerCount: Number(user.follower_count ?? 0),
      followingCount: Number(user.following_count ?? 0),
      likesCount: Number(user.likes_count ?? 0),
      videoCount: Number(user.video_count ?? 0),
      totalViews: totals.views,
      totalVideoLikes: totals.likes,
      totalComments: totals.comments,
      totalShares: totals.shares
    })
  } catch (e) {
    const msg = e instanceof TikTokApiError ? e.message : String(e)
    const response = redirect(`?auth_error=${encodeURIComponent(msg.slice(0, 200))}`)
    response.cookies.delete(OAUTH_COOKIE)
    return response
  }

  const response = redirect('?connected=1')
  response.cookies.delete(OAUTH_COOKIE)
  return response
}
