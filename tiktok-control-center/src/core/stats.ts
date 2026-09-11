import type { StatsFile } from './types'

export function emptyStats (): StatsFile {
  return { version: 1, days: {} }
}

/** Cle de jour locale au format AAAA-MM-JJ. */
export function dayKey (date: Date): string {
  const year = date.getFullYear()
  const month = String(date.getMonth() + 1).padStart(2, '0')
  const day = String(date.getDate()).padStart(2, '0')
  return `${year}-${month}-${day}`
}

export function addSeconds (
  stats: StatsFile, day: string, accountId: string, seconds: number
): StatsFile {
  const dayEntry = stats.days[day] ?? {}
  return {
    ...stats,
    days: {
      ...stats.days,
      [day]: { ...dayEntry, [accountId]: (dayEntry[accountId] ?? 0) + seconds }
    }
  }
}

export function secondsFor (stats: StatsFile, day: string, accountId: string): number {
  return stats.days[day]?.[accountId] ?? 0
}

/** Supprime les jours strictement anterieurs a `cutoffDay`. Les cles AAAA-MM-JJ se comparent lexicographiquement. */
export function purgeOlderThan (stats: StatsFile, cutoffDay: string): StatsFile {
  const days: StatsFile['days'] = {}
  for (const [day, entry] of Object.entries(stats.days)) {
    if (day >= cutoffDay) days[day] = entry
  }
  return { ...stats, days }
}

/**
 * Normalise un contenu de fichier de stats lu sur disque. Miroir de
 * `migrate()` (accounts.ts) : ne leve jamais, retombe sur un fichier vide
 * pour tout ce qui n'est pas reconnaissable, et n'ecarte que les entrees
 * individuellement malformees plutot que tout le fichier.
 */
export function migrateStats (raw: unknown): StatsFile {
  if (typeof raw !== 'object' || raw === null) return emptyStats()
  const candidate = raw as Partial<StatsFile>
  if (candidate.version !== 1) return emptyStats()
  if (typeof candidate.days !== 'object' || candidate.days === null || Array.isArray(candidate.days)) {
    return emptyStats()
  }

  const days: StatsFile['days'] = {}
  for (const [day, entry] of Object.entries(candidate.days as Record<string, unknown>)) {
    if (typeof entry !== 'object' || entry === null || Array.isArray(entry)) continue

    const accounts: Record<string, number> = {}
    for (const [accountId, seconds] of Object.entries(entry as Record<string, unknown>)) {
      if (typeof seconds === 'number' && Number.isFinite(seconds)) {
        accounts[accountId] = seconds
      }
    }
    days[day] = accounts
  }
  return { version: 1, days }
}
