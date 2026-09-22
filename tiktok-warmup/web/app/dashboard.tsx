'use client'

import { useCallback, useEffect, useState } from 'react'
import type { DashboardPayload, PendingFyp } from '@/lib/types'

const EMPTY: DashboardPayload = {
  agent: {
    lastSeenAt: null,
    iphone: false,
    wdaReady: false,
    wdaUrl: null,
    message: 'Connexion…',
  },
  accounts: {},
  pendingFyp: [],
  queued: [],
  agentOnline: false,
}

export default function Dashboard () {
  const [data, setData] = useState<DashboardPayload>(EMPTY)
  const [auth, setAuth] = useState<'unknown' | 'ok' | 'login'>('unknown')
  const [password, setPassword] = useState('')
  const [loginError, setLoginError] = useState('')
  const [fypDrafts, setFypDrafts] = useState<Record<number, string>>({})
  const [busy, setBusy] = useState(false)

  const refresh = useCallback(async () => {
    const resp = await fetch('/api/status', { cache: 'no-store' })
    if (resp.status === 401) {
      setAuth('login')
      return
    }
    if (!resp.ok) return
    setAuth('ok')
    setData(await resp.json())
  }, [])

  useEffect(() => {
    refresh()
    const id = setInterval(refresh, 2500)
    return () => clearInterval(id)
  }, [refresh])

  async function login (e: React.FormEvent) {
    e.preventDefault()
    setLoginError('')
    const resp = await fetch('/api/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ password }),
    })
    if (!resp.ok) {
      setLoginError('Mot de passe incorrect')
      return
    }
    setPassword('')
    await refresh()
  }

  async function post (url: string, body?: unknown) {
    setBusy(true)
    try {
      await fetch(url, {
        method: 'POST',
        headers: body ? { 'Content-Type': 'application/json' } : undefined,
        body: body ? JSON.stringify(body) : undefined,
      })
      await refresh()
    } finally {
      setBusy(false)
    }
  }

  if (auth === 'unknown') {
    return <div style={{ padding: 40, color: '#888' }}>Chargement…</div>
  }

  if (auth === 'login') {
    return (
      <div className="login-wrap">
        <form className="login-card" onSubmit={login}>
          <h1>TikTok Warmup</h1>
          <p>Dashboard Peachtint — saisis le mot de passe Vercel.</p>
          <input
            type="password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            placeholder="Mot de passe"
            autoFocus
          />
          {loginError ? <div className="login-error">{loginError}</div> : null}
          <button type="submit" className="btn btn-start">Entrer</button>
        </form>
        <style>{loginCss}</style>
      </div>
    )
  }

  const { agent, accounts, pendingFyp, queued, agentOnline } = data
  const ready = agentOnline && agent.iphone && agent.wdaReady

  return (
    <>
      <header>
        <div>
          <h1>TikTok Warmup</h1>
          <div className="sub">Protocole Peachtint · iPhone XS</div>
        </div>
        <div className="controls">
          <button className="btn btn-start" disabled={busy || !ready} onClick={() => post('/api/start-all')}>
            Start All
          </button>
          <button className="btn btn-stop" disabled={busy} onClick={() => post('/api/stop-all')}>
            Stop All
          </button>
        </div>
      </header>

      <section className={`agent ${ready ? 'ready' : agentOnline ? 'wait' : 'off'}`}>
        <div className="agent-title">
          {ready ? 'Prêt' : agentOnline ? 'Mac en ligne' : 'Mac hors ligne'}
        </div>
        <div className="pills">
          <span className={`pill ${agentOnline ? 'on' : ''}`}>Mac</span>
          <span className={`pill ${agent.iphone ? 'on' : ''}`}>iPhone</span>
          <span className={`pill ${agent.wdaReady ? 'on' : ''}`}>WDA</span>
        </div>
        <p>
          {agentOnline
            ? agent.message || (ready ? 'Branche rien d’autre — clique Start.' : 'En attente de l’iPhone / WDA.')
            : 'Branche l’iPhone en USB, puis sur le Mac : python -m agent'}
        </p>
        {queued.length > 0 ? (
          <p className="queue">{queued.length} ordre{queued.length > 1 ? 's' : ''} en file</p>
        ) : null}
      </section>

      {pendingFyp.length > 0 ? (
        <section className="fyp-box">
          <h2>Comptage FYP en attente</h2>
          {pendingFyp.map((row: PendingFyp) => (
            <form
              key={row.session_id}
              className="fyp-row"
              onSubmit={e => {
                e.preventDefault()
                const count = Number(fypDrafts[row.session_id] ?? '')
                if (!Number.isInteger(count)) return
                post(`/api/fyp/${row.session_id}`, { count })
              }}
            >
              <span>
                {row.username} · session #{row.session_id}
                {row.keyword ? ` · « ${row.keyword} »` : ''}
              </span>
              <input
                type="number"
                min={0}
                max={20}
                placeholder="niche / 20"
                value={fypDrafts[row.session_id] ?? ''}
                onChange={e => setFypDrafts(d => ({ ...d, [row.session_id]: e.target.value }))}
              />
              <button className="btn btn-start btn-sm" type="submit">Enregistrer</button>
            </form>
          ))}
        </section>
      ) : null}

      <div className="grid">
        {Object.entries(accounts).map(([username, info]) => (
          <article className="card" key={username} id={`card-${username}`}>
            <div className="card-header">
              <h2>{username}</h2>
              <span className={`status status-${info.status}`}>{info.status}</span>
            </div>
            <div className="protocol-line">
              <span className="tag">{info.role}</span>
              {info.protected ? <span className="tag tag-locked">ne pas toucher</span> : null}
              <span>Jour {info.protocol_day} / 14</span>
              {info.last_session?.fyp_verdict ? (
                <span className={`tag tag-${info.last_session.fyp_verdict}`}>
                  FYP {info.last_session.fyp_verdict}
                </span>
              ) : null}
            </div>
            {info.last_session?.keyword ? (
              <div className="ramp-up-info">
                dernière session : <span className="keyword">« {info.last_session.keyword} »</span>
                {!info.last_session.completed ? ' — interrompue' : ''}
              </div>
            ) : null}
            <div className="ramp-up-info caps">
              24 h :{' '}
              <b className={info.used_24h.likes >= info.caps_24h.likes[1] ? 'over' : ''}>
                {info.used_24h.likes}
              </b>
              /{info.caps_24h.likes[0]}–{info.caps_24h.likes[1]} likes ·{' '}
              <b className={info.used_24h.follows >= info.caps_24h.follows[1] ? 'over' : ''}>
                {info.used_24h.follows}
              </b>
              /{info.caps_24h.follows[0]}–{info.caps_24h.follows[1]} abos ·{' '}
              <b className={info.used_24h.comments >= info.caps_24h.comments[1] ? 'over' : ''}>
                {info.used_24h.comments}
              </b>
              /{info.caps_24h.comments[1]} comm.
            </div>
            <div className="counters">
              <div className="counter">
                <strong>{info.counters.videos_watched}</strong>
                Videos
              </div>
              <div className="counter">
                <strong>{info.counters.likes}</strong>
                Likes
              </div>
              <div className="counter">
                <strong>{info.counters.follows}</strong>
                Follows
              </div>
              <div className="counter">
                <strong>{info.counters.comments}</strong>
                Comments
              </div>
            </div>
            <div className="card-controls">
              {info.protected ? (
                <span className="ramp-up-info">Aucun warmup sur ce compte.</span>
              ) : (
                <>
                  <button
                    className="btn btn-start btn-sm"
                    disabled={busy || !ready}
                    onClick={() => post(`/api/start/${username}`)}
                  >
                    Start
                  </button>
                  <button
                    className="btn btn-stop btn-sm"
                    disabled={busy}
                    onClick={() => post(`/api/stop/${username}`)}
                  >
                    Stop
                  </button>
                </>
              )}
            </div>
            <div className="logs">
              {info.recent_logs.map((log, i) => (
                <div className="log-entry" key={`${log.time}-${i}`}>
                  <span className="time">{(log.time || '').slice(11, 19)}</span>
                  <span className="action">{log.action}</span>
                  {log.detail}
                </div>
              ))}
            </div>
          </article>
        ))}
      </div>
      <style>{dashCss}</style>
    </>
  )
}

const loginCss = `
.login-wrap { min-height: 100vh; display: grid; place-items: center; padding: 24px; }
.login-card { width: min(420px, 100%); background: #1a1a1a; border: 1px solid #2a2a2a; border-radius: 16px; padding: 28px; display: grid; gap: 14px; }
.login-card h1 { font-size: 22px; }
.login-card p { color: #888; font-size: 14px; }
.login-card input { background: #111; border: 1px solid #333; color: #fff; border-radius: 8px; padding: 12px; }
.login-error { color: #e08c8c; font-size: 13px; }
`

const dashCss = `
header { padding: 20px 30px; display: flex; justify-content: space-between; align-items: center; border-bottom: 1px solid #2a2a2a; gap: 16px; flex-wrap: wrap; }
header h1 { font-size: 22px; font-weight: 600; }
.sub { color: #666; font-size: 12px; margin-top: 4px; }
.controls { display: flex; gap: 10px; }
.btn { padding: 10px 24px; border: none; border-radius: 8px; font-size: 14px; font-weight: 600; cursor: pointer; }
.btn:hover { opacity: 0.85; }
.btn:disabled { opacity: 0.35; cursor: not-allowed; }
.btn-start { background: #25d366; color: #000; }
.btn-stop { background: #e74c3c; color: #fff; }
.btn-sm { padding: 6px 14px; font-size: 12px; }
.agent { margin: 20px 30px 0; padding: 16px 18px; border-radius: 12px; border: 1px solid #2a2a2a; background: #1a1a1a; }
.agent.ready { border-color: #25d36655; }
.agent.wait { border-color: #ddc46a55; }
.agent.off { border-color: #e08c8c55; }
.agent-title { font-weight: 600; margin-bottom: 8px; }
.pills { display: flex; gap: 8px; margin-bottom: 8px; }
.pill { font-size: 11px; text-transform: uppercase; letter-spacing: .06em; padding: 3px 8px; border-radius: 99px; background: #2a2a2a; color: #777; }
.pill.on { background: #1e3a2a; color: #6cd39a; }
.agent p { color: #aaa; font-size: 13px; }
.queue { margin-top: 8px; color: #8ab4f8 !important; }
.fyp-box { margin: 16px 30px 0; padding: 16px; border-radius: 12px; background: #1a1a1a; border: 1px solid #2a2a2a; }
.fyp-box h2 { font-size: 14px; margin-bottom: 12px; }
.fyp-row { display: flex; gap: 10px; align-items: center; flex-wrap: wrap; margin-bottom: 8px; font-size: 13px; }
.fyp-row input { width: 90px; background: #111; border: 1px solid #333; color: #fff; border-radius: 6px; padding: 6px 8px; }
.grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(280px, 1fr)); gap: 16px; padding: 20px 30px; }
.card { background: #1a1a1a; border-radius: 12px; padding: 20px; border: 1px solid #2a2a2a; }
.card-header { display: flex; justify-content: space-between; align-items: center; margin-bottom: 16px; }
.card-header h2 { font-size: 16px; font-weight: 600; }
.status { padding: 3px 10px; border-radius: 12px; font-size: 11px; font-weight: 600; text-transform: uppercase; }
.status-idle { background: #333; color: #888; }
.status-running { background: #25d36622; color: #25d366; }
.status-error { background: #e74c3c22; color: #e74c3c; }
.counters { display: grid; grid-template-columns: repeat(2, 1fr); gap: 8px; margin-bottom: 16px; }
.counter { background: #222; padding: 8px 12px; border-radius: 8px; font-size: 12px; }
.counter strong { display: block; font-size: 18px; color: #fff; }
.logs { max-height: 200px; overflow-y: auto; font-size: 12px; font-family: ui-monospace, SFMono-Regular, Menlo, monospace; background: #111; border-radius: 8px; padding: 10px; margin-top: 12px; }
.log-entry { padding: 3px 0; border-bottom: 1px solid #1a1a1a; color: #aaa; }
.log-entry .time { color: #666; margin-right: 6px; }
.log-entry .action { color: #25d366; margin-right: 6px; }
.card-controls { margin-top: 12px; display: flex; gap: 8px; }
.ramp-up-info { font-size: 12px; color: #666; margin-bottom: 12px; }
.protocol-line { display: flex; align-items: center; gap: 8px; flex-wrap: wrap; font-size: 12px; color: #666; margin-bottom: 12px; }
.tag { font-size: 10px; letter-spacing: .08em; text-transform: uppercase; padding: 2px 6px; border-radius: 3px; background: #2a2a2a; color: #aaa; }
.tag-locked { background: #4a2a12; color: #e0a45c; }
.tag-cold { background: #3a2a2a; color: #e08c8c; }
.tag-warming { background: #3a3520; color: #ddc46a; }
.tag-ready { background: #1e3a2a; color: #6cd39a; }
.keyword { color: #8ab4f8; }
.caps { font-variant-numeric: tabular-nums; }
.caps b { color: #ddd; font-weight: 600; }
.caps .over { color: #e08c8c; }
`
