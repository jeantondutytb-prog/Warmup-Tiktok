import { NextRequest, NextResponse } from 'next/server'
import { getSettings } from '@/lib/config'
import { consumeOAuthState, upsertAccount } from '@/lib/db'
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

  if (error) {
    return NextResponse.redirect(new URL(`/?auth_error=${encodeURIComponent(error)}`, settings.appBaseUrl))
  }
  if (!code) {
    return NextResponse.redirect(new URL('/?auth_error=missing_code', settings.appBaseUrl))
  }

  const codeVerifier = await consumeOAuthState(state)
  if (!codeVerifier) {
    return NextResponse.redirect(new URL('/?auth_error=invalid_state', settings.appBaseUrl))
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
    const msg = e instanceof TikTokApiError ? e.message : 'oauth_failed'
    return NextResponse.redirect(
      new URL(`/?auth_error=${encodeURIComponent(msg.slice(0, 200))}`, settings.appBaseUrl)
    )
  }

  return NextResponse.redirect(new URL('/?connected=1', settings.appBaseUrl))
}
