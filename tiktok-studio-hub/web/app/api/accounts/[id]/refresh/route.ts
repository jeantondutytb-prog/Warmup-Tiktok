import { NextResponse } from 'next/server'
import { getSettings } from '@/lib/config'
import { getAccount, updateAccountStats } from '@/lib/db'
import {
  fetchAllVideos,
  fetchUserInfo,
  sumVideos,
  TikTokApiError
} from '@/lib/tiktok'

export async function POST (
  _request: Request,
  { params }: { params: Promise<{ id: string }> }
) {
  const { id } = await params
  const account = await getAccount(Number(id))
  if (!account) return NextResponse.json({ error: 'Compte introuvable' }, { status: 404 })

  const settings = getSettings()
  try {
    const user = await fetchUserInfo(account.access_token)
    const videos = await fetchAllVideos(account.access_token)
    const totals = sumVideos(videos)
    await updateAccountStats(account.id, {
      displayName: String(user.display_name ?? account.display_name),
      avatarUrl: String(user.avatar_url ?? account.avatar_url),
      accessToken: account.access_token,
      refreshToken: account.refresh_token,
      followerCount: Number(user.follower_count ?? 0),
      followingCount: Number(user.following_count ?? 0),
      likesCount: Number(user.likes_count ?? 0),
      videoCount: Number(user.video_count ?? 0),
      totalViews: totals.views,
      totalVideoLikes: totals.likes,
      totalComments: totals.comments,
      totalShares: totals.shares
    })
    return NextResponse.json({ ok: true })
  } catch (e) {
    const msg = e instanceof TikTokApiError ? e.message : 'sync_failed'
    return NextResponse.json({ error: msg }, { status: 502 })
  }
}
