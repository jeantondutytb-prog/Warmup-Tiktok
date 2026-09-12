import { NextResponse } from 'next/server'
import { getSettings } from '@/lib/config'
import { buildDashboard, getAccount, listAccounts, updateAccountStats } from '@/lib/db'
import {
  fetchAllVideos,
  fetchUserInfo,
  sumVideos,
  TikTokApiError
} from '@/lib/tiktok'

export async function POST () {
  const settings = getSettings()
  const rows = await listAccounts()
  const errors: string[] = []

  for (const account of rows) {
    if (account.access_token === 'demo') continue
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
    } catch (e) {
      const msg = e instanceof TikTokApiError ? e.message : 'sync_failed'
      errors.push(`${account.display_name}: ${msg}`)
    }
  }

  const updated = await listAccounts()
  return NextResponse.json({ ...buildDashboard(updated), errors })
}
