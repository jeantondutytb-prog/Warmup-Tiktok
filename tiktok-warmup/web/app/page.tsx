import { Suspense } from 'react'
import Dashboard from './dashboard'

export default function Page () {
  return (
    <Suspense fallback={<div style={{ padding: 40, color: '#888' }}>Chargement…</div>}>
      <Dashboard />
    </Suspense>
  )
}
