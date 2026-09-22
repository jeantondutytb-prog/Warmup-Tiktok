'use client'

import { useCallback, useEffect, useState } from 'react'
import type { DashboardPayload } from '@/lib/types'

const EMPTY: DashboardPayload = {
  agent: {
    lastSeenAt: null,
    iphone: false,
    wdaReady: false,
    wdaUrl: null,
    message: 'Connexion…',
    warmupRunning: false,
  },
  accounts: {},
  pendingFyp: [],
  queued: [],
  agentOnline: false,
}

function statusLine (data: DashboardPayload): { text: string; tone: 'ok' | 'wait' | 'off' | 'run' } {
  const { agent, agentOnline } = data
  if (!agentOnline) {
    return { text: 'Mac hors ligne', tone: 'off' }
  }
  if (agent.warmupRunning) {
    return { text: 'Warm up en cours sur l’iPhone…', tone: 'run' }
  }
  if (!agent.iphone) {
    return { text: 'Branche l’iPhone en USB et déverrouille-le', tone: 'wait' }
  }
  if (!agent.wdaReady) {
    return { text: agent.message || 'Préparation de l’iPhone…', tone: 'wait' }
  }
  if (data.queued.length > 0) {
    return { text: 'Démarrage…', tone: 'wait' }
  }
  return { text: 'Prêt — clique Start Warm Up', tone: 'ok' }
}

export default function Dashboard () {
  const [data, setData] = useState<DashboardPayload>(EMPTY)
  const [auth, setAuth] = useState<'unknown' | 'ok' | 'login'>('unknown')
  const [password, setPassword] = useState('')
  const [loginError, setLoginError] = useState('')
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
    const id = setInterval(refresh, 2000)
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

  async function post (url: string) {
    setBusy(true)
    try {
      await fetch(url, { method: 'POST' })
      await refresh()
    } finally {
      setBusy(false)
    }
  }

  if (auth === 'unknown') {
    return <div className="screen muted">Chargement…</div>
  }

  if (auth === 'login') {
    return (
      <div className="screen center">
        <form className="login-card" onSubmit={login}>
          <h1>Warmup Peachtint</h1>
          <input
            type="password"
            value={password}
            onChange={e => setPassword(e.target.value)}
            placeholder="Mot de passe"
            autoFocus
          />
          {loginError ? <p className="err">{loginError}</p> : null}
          <button type="submit" className="btn start">Entrer</button>
        </form>
        <style>{css}</style>
      </div>
    )
  }

  const { agent, agentOnline } = data
  const status = statusLine(data)
  const ready = agentOnline && agent.iphone && agent.wdaReady && !agent.warmupRunning
  const canStop = agentOnline && (agent.warmupRunning || data.queued.length > 0)

  return (
    <div className="screen center">
      <main className="panel">
        <h1>Warmup Peachtint</h1>
        <p className={`status tone-${status.tone}`}>{status.text}</p>

        <div className="actions">
          <button
            type="button"
            className="btn start big"
            disabled={busy || !ready}
            onClick={() => post('/api/warmup/start')}
          >
            Start Warm Up
          </button>
          <button
            type="button"
            className="btn stop big"
            disabled={busy || !canStop}
            onClick={() => post('/api/warmup/stop')}
          >
            Stop
          </button>
        </div>
      </main>
      <style>{css}</style>
    </div>
  )
}

const css = `
.screen { min-height: 100vh; background: #0f0f0f; color: #e8e8e8; }
.center { display: grid; place-items: center; padding: 24px; }
.muted { padding: 40px; color: #888; }
.panel { width: min(420px, 100%); text-align: center; }
.panel h1 { font-size: 28px; font-weight: 600; margin-bottom: 20px; }
.status { font-size: 15px; line-height: 1.5; margin-bottom: 32px; min-height: 3em; }
.tone-ok { color: #6cd39a; }
.tone-wait { color: #ddc46a; }
.tone-off { color: #e08c8c; }
.tone-run { color: #8ab4f8; }
.actions { display: grid; gap: 14px; }
.btn { border: none; border-radius: 14px; font-size: 17px; font-weight: 700; cursor: pointer; padding: 18px 24px; }
.btn:disabled { opacity: 0.35; cursor: not-allowed; }
.btn.start { background: #25d366; color: #000; }
.btn.stop { background: #e74c3c; color: #fff; }
.btn.big { padding: 22px 28px; font-size: 20px; }
.login-card { width: min(360px, 100%); display: grid; gap: 14px; }
.login-card h1 { font-size: 24px; text-align: center; }
.login-card input { background: #1a1a1a; border: 1px solid #333; color: #fff; border-radius: 10px; padding: 14px; font-size: 16px; }
.err { color: #e08c8c; font-size: 14px; text-align: center; }
`
