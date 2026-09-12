'use client'

import { useCallback, useEffect, useState } from 'react'
import { useSearchParams } from 'next/navigation'

type Account = {
  id: number
  display_name: string
  avatar_url: string
  follower_count: number
  total_views: number
  total_video_likes: number
  total_comments: number
  video_count: number
  last_synced_at: string | null
  is_demo: boolean
}

type Dashboard = {
  totals: Record<string, number>
  accounts: Account[]
}

const fmt = (n: number | null | undefined) => {
  if (n == null || Number.isNaN(n)) return '—'
  if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`
  if (n >= 1_000) return `${(n / 1_000).toFixed(1)}K`
  return String(n)
}

export default function Dashboard () {
  const searchParams = useSearchParams()
  const [view, setView] = useState<'analytics' | 'accounts'>('analytics')
  const [data, setData] = useState<Dashboard | null>(null)
  const [banner, setBanner] = useState<{ text: string; type: string } | null>(null)
  const [oauthOk, setOauthOk] = useState(false)

  const load = useCallback(async () => {
    const cfg = await fetch('/api/config').then(r => r.json())
    setOauthOk(cfg.oauth_configured)
    const dash = await fetch('/api/dashboard').then(r => r.json())
    if (dash.error) {
      setBanner({ text: `Base de données : ${dash.error}. Ajoutez Postgres dans Vercel → Storage.`, type: 'info' })
      setData({ totals: { accounts: 0, followers: 0, views: 0, likes: 0, comments: 0, shares: 0, videos: 0, profile_likes: 0, following: 0 }, accounts: [] })
      return
    }
    setData(dash)
  }, [])

  useEffect(() => {
    load()
    const err = searchParams.get('auth_error')
    const ok = searchParams.get('connected')
    if (err) setBanner({ text: `Connexion échouée : ${err}`, type: 'error' })
    else if (ok) setBanner({ text: 'Compte TikTok connecté avec succès.', type: 'success' })
  }, [load, searchParams])

  const refreshAll = async () => {
    const resp = await fetch('/api/refresh-all', { method: 'POST' })
    const json = await resp.json()
    setData(json)
    if (json.errors?.length) setBanner({ text: json.errors.join(' · '), type: 'error' })
  }

  const t = data?.totals

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="brand">
          <svg className="logo" viewBox="0 0 48 48" aria-hidden="true">
            <path fill="#25F4EE" d="M19 8v26.5c0 3.6-2.9 6.5-6.5 6.5S6 38.1 6 34.5 8.9 28 12.5 28c.9 0 1.8.2 2.5.5V20.8a10.4 10.4 0 0 0-2.5-.3C5.1 20.5 0 25.6 0 32.5S5.1 44.5 12 44.5 22 39.4 22 32.5V8h7z"/>
            <path fill="#FE2C55" d="M36 8v26.5c0 3.6-2.9 6.5-6.5 6.5S23 38.1 23 34.5 25.9 28 29.5 28c.9 0 1.8.2 2.5.5V20.8a10.4 10.4 0 0 0-2.5-.3c-4.9 0-9 5.1-9 12 0 6.9 5.1 12 12 12s12-5.1 12-12V8h-7z"/>
          </svg>
          <div>
            <strong>TikTok Studio</strong>
            <span>Stats réunies</span>
          </div>
        </div>
        <nav className="nav">
          <button className={`nav-item ${view === 'analytics' ? 'active' : ''}`} onClick={() => setView('analytics')}>📊 Analytiques</button>
          <button className={`nav-item ${view === 'accounts' ? 'active' : ''}`} onClick={() => setView('accounts')}>👤 Comptes</button>
        </nav>
        <div className="sidebar-footer">
          {oauthOk && <a className="btn-primary" href="/auth/login">+ Ajouter un compte</a>}
          <p className="hint">{oauthOk ? 'Connectez chaque compte TikTok via OAuth.' : 'Clés TikTok manquantes dans les variables Vercel.'}</p>
        </div>
      </aside>

      <main className="main">
        <header className="topbar">
          <div>
            <h1>{view === 'accounts' ? 'Comptes' : 'Analytiques'}</h1>
            <p className="subtitle">Tous vos comptes TikTok en un seul endroit</p>
          </div>
          <button className="btn-ghost" onClick={refreshAll}>Actualiser</button>
        </header>

        {banner && <div className={`banner ${banner.type}`}>{banner.text}</div>}

        {view === 'analytics' && t && (
          <section className="view active">
            <div className="stats-grid">
              <article className="stat-card highlight"><span className="label">Vues totales</span><strong>{fmt(t.views)}</strong></article>
              <article className="stat-card"><span className="label">Abonnés</span><strong>{fmt(t.followers)}</strong></article>
              <article className="stat-card"><span className="label">J&apos;aime</span><strong>{fmt(t.likes)}</strong></article>
              <article className="stat-card"><span className="label">Comptes</span><strong>{fmt(t.accounts)}</strong></article>
            </div>
            <section className="panel">
              <div className="panel-head"><h2>Répartition par compte</h2></div>
              <div className="table-wrap">
                <table>
                  <thead><tr><th>Compte</th><th>Abonnés</th><th>Vues</th><th>J&apos;aime</th><th>Vidéos</th></tr></thead>
                  <tbody>
                    {!data?.accounts.length ? (
                      <tr><td colSpan={5} style={{ textAlign: 'center', color: '#888', padding: 32 }}>Aucun compte — cliquez « + Ajouter un compte »</td></tr>
                    ) : data.accounts.map(a => (
                      <tr key={a.id}><td>@{a.display_name}</td><td>{fmt(a.follower_count)}</td><td>{fmt(a.total_views)}</td><td>{fmt(a.total_video_likes)}</td><td>{fmt(a.video_count)}</td></tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </section>
          </section>
        )}

        {view === 'accounts' && (
          <div className="accounts-grid">
            {!data?.accounts.length ? (
              <article className="account-card" style={{ gridColumn: '1/-1', textAlign: 'center', padding: 40, color: '#888' }}>
                Aucun compte connecté.<br /><br />
                {oauthOk && <a className="btn-primary" href="/auth/login" style={{ display: 'inline-block', width: 'auto', padding: '12px 24px' }}>+ Ajouter un compte</a>}
              </article>
            ) : data.accounts.map(a => (
              <article className="account-card" key={a.id}>
                <div className="account-card-head"><h3>@{a.display_name}</h3></div>
                <div className="account-card-stats">
                  <div className="mini-stat"><span>Abonnés</span><b>{fmt(a.follower_count)}</b></div>
                  <div className="mini-stat"><span>Vues</span><b>{fmt(a.total_views)}</b></div>
                </div>
              </article>
            ))}
          </div>
        )}
      </main>
    </div>
  )
}
