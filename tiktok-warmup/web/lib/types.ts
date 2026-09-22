export interface AccountCounters {
  likes: number
  follows: number
  comments: number
  videos_watched: number
  scrolls: number
}

export interface LastSession {
  id: number
  keyword: string | null
  started_at: string
  completed: boolean
  fyp_niche_count: number | null
  fyp_verdict: string | null
}

export interface AccountStatus {
  status: string
  ramp_up_day: number
  protocol_day: number
  role: string
  protected: boolean
  used_24h: { likes: number; follows: number; comments: number }
  caps_24h: {
    likes: [number, number]
    follows: [number, number]
    comments: [number, number]
  }
  last_session: LastSession | null
  counters: AccountCounters
  recent_logs: { action: string; detail: string; time: string }[]
}

export interface AgentHeartbeat {
  lastSeenAt: string | null
  iphone: boolean
  wdaReady: boolean
  wdaUrl: string | null
  message: string
}

export type JobType = 'start' | 'start-all' | 'stop-all' | 'fyp' | 'protocol-day'

export interface Job {
  id: number
  type: JobType
  username?: string
  force?: boolean
  sessionId?: number
  count?: number
  day?: number
  createdAt: string
  claimedAt?: string
}

export interface WarmupEvent {
  type: string
  username?: string
  data?: string
  timestamp: string
}

export interface PendingFyp {
  session_id: number
  username: string
  keyword: string | null
  started_at: string
  shots_dir?: string
}

export interface StoreFile {
  agent: AgentHeartbeat
  accounts: Record<string, AccountStatus>
  jobs: Job[]
  nextJobId: number
  events: WarmupEvent[]
  pendingFyp: PendingFyp[]
}

export interface DashboardPayload {
  agent: AgentHeartbeat
  accounts: Record<string, AccountStatus>
  pendingFyp: PendingFyp[]
  queued: Job[]
  agentOnline: boolean
}
