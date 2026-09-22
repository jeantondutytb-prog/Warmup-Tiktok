import type { Metadata } from 'next'
import './globals.css'

export const metadata: Metadata = {
  title: 'TikTok Warmup',
  description: 'Dashboard Peachtint — sessions iPhone depuis Vercel',
}

export default function RootLayout ({ children }: { children: React.ReactNode }) {
  return (
    <html lang="fr">
      <body>{children}</body>
    </html>
  )
}
