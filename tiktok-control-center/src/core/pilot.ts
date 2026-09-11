import type { Account, StatsFile } from './types'
import { dayKey, secondsFor } from './stats'

/** Largeur de la fenetre glissante utilisee par regularityScore, en jours. */
export const WINDOW_DAYS = 14

const MS_PER_DAY = 24 * 60 * 60 * 1000

/**
 * Ligne de tableau de bord pour un compte : tout ce dont le rendu a besoin,
 * deja calcule, pour eviter que le renderer ne doive re-deriver quoi que ce
 * soit a partir de StatsFile/AccountsFile.
 */
export interface PilotEntry {
  account: Account
  /** Secondes deja enregistrees aujourd'hui pour ce compte. */
  secondsToday: number
  /** Objectif du jour converti en secondes (dailyGoalMinutes * 60). */
  goalSeconds: number
  /** Jours ecoules depuis la derniere session avec activite, null si aucune session n'existe. */
  daysSinceLastSession: number | null
  /** Score de regularite 0..100, voir regularityScore. */
  regularityScore: number
}

function startOfDay (date: Date): Date {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate())
}

/** Difference en jours calendaires locaux entre deux dates (to - from). */
function daysBetween (from: Date, to: Date): number {
  return Math.round((startOfDay(to).getTime() - startOfDay(from).getTime()) / MS_PER_DAY)
}

/** Cles de jour (AAAA-MM-JJ) de la fenetre de WINDOW_DAYS jours se terminant le jour donne, du plus ancien au plus recent. */
function windowDayKeys (today: Date): string[] {
  const keys: string[] = []
  for (let offset = WINDOW_DAYS - 1; offset >= 0; offset--) {
    const d = new Date(today.getFullYear(), today.getMonth(), today.getDate() - offset)
    keys.push(dayKey(d))
  }
  return keys
}

/** Longueur de la plus longue serie de valeurs `false` consecutives. */
function longestFalseRun (flags: boolean[]): number {
  let longest = 0
  let current = 0
  for (const active of flags) {
    if (active) {
      current = 0
    } else {
      current += 1
      longest = Math.max(longest, current)
    }
  }
  return longest
}

/**
 * Score de REGULARITE, 0..100, pour un compte sur les WINDOW_DAYS derniers
 * jours (jour donne inclus).
 *
 * Ce n'est PAS un score de confiance TikTok : il ne consulte aucun signal de
 * la plateforme (pas de vues, pas de statut du compte, pas de risque de ban).
 * Il mesure uniquement la constance du proprietaire lui-meme - est-ce qu'il
 * s'est presente, et quand il s'est presente, est-ce qu'il a fait le travail.
 * Un compte peut avoir un score de regularite de 100 et etre banni cote
 * TikTok une minute plus tard ; ce module n'a aucun moyen de le savoir.
 *
 * Composition (chaque terme documente sur sa propre ligne) :
 * - attendance   : proportion de jours actifs sur la fenetre -> s'est-il presente.
 * - attainment   : moyenne, sur les seuls jours actifs, de min(1, secondes/objectif)
 *                  -> quand il s'est presente, a-t-il fait le travail. Moyenner sur
 *                  les jours actifs seulement (et non les WINDOW_DAYS jours) est
 *                  deliberement independant de l'attendance, pour ne pas compter
 *                  l'absence deux fois.
 * - gapPenalty   : plus longue serie de jours consecutifs sans activite dans la
 *                  fenetre, normalisee -> penalise les longues coupures meme si le
 *                  total d'attendance est correct.
 * - maturity     : plafonne les comptes jeunes, pour qu'un seul jour actif sur un
 *                  compte cree avant-hier ne puisse pas atteindre 100.
 */
export function regularityScore (account: Account, stats: StatsFile, today: Date): number {
  const goalSeconds = account.dailyGoalMinutes * 60
  const secondsPerDay = windowDayKeys(today).map(day => secondsFor(stats, day, account.id))
  const activeFlags = secondsPerDay.map(seconds => seconds > 0)
  const activeCount = activeFlags.filter(Boolean).length

  // attendance : s'est-il presente ?
  const attendance = activeCount / WINDOW_DAYS

  // attainment : quand il s'est presente, a-t-il fait le travail ? 0 si aucun jour actif.
  const attainment = activeCount === 0
    ? 0
    : secondsPerDay.reduce((sum, seconds, i) => (
      activeFlags[i] ? sum + Math.min(1, seconds / goalSeconds) : sum
    ), 0) / activeCount

  // gapPenalty : plus longue coupure consecutive dans la fenetre.
  const longestGapDays = longestFalseRun(activeFlags)
  const gapPenalty = Math.min(1, longestGapDays / WINDOW_DAYS)

  // maturity : plafonne les comptes trop jeunes pour avoir rempli la fenetre.
  const daysSinceCreation = Math.max(0, daysBetween(new Date(account.createdAt), today))
  const maturity = Math.min(1, daysSinceCreation / WINDOW_DAYS)

  const raw = 0.55 * attendance + 0.45 * attainment - 0.25 * gapPenalty
  const clamped = Math.min(1, Math.max(0, raw))
  return Math.round(100 * maturity * clamped)
}

/** Cle du jour le plus recent avec une activite enregistree pour ce compte, sur tout StatsFile, ou null si aucune. */
function lastActiveDayKey (account: Account, stats: StatsFile): string | null {
  let latest: string | null = null
  for (const [day, entry] of Object.entries(stats.days)) {
    if ((entry[account.id] ?? 0) > 0 && (latest === null || day > latest)) {
      latest = day
    }
  }
  return latest
}

function dayKeyToLocalDate (key: string): Date {
  const [year, month, day] = key.split('-').map(Number)
  return new Date(year, month - 1, day)
}

/** Construit la ligne de tableau de bord pour un seul compte. */
export function pilotEntryFor (account: Account, stats: StatsFile, today: Date): PilotEntry {
  const todayKey = dayKey(today)
  const lastDay = lastActiveDayKey(account, stats)
  return {
    account,
    secondsToday: secondsFor(stats, todayKey, account.id),
    goalSeconds: account.dailyGoalMinutes * 60,
    daysSinceLastSession: lastDay === null ? null : daysBetween(dayKeyToLocalDate(lastDay), today),
    regularityScore: regularityScore(account, stats, today)
  }
}

function compareEntries (a: PilotEntry, b: PilotEntry): number {
  // 1. Un objectif du jour deja atteint releque toujours en bas.
  const aMet = a.secondsToday >= a.goalSeconds
  const bMet = b.secondsToday >= b.goalSeconds
  if (aMet !== bMet) return aMet ? 1 : -1

  // 2. Plus longue absence d'abord ; jamais travaille = negligence maximale.
  const aNeglect = a.daysSinceLastSession === null ? Number.POSITIVE_INFINITY : a.daysSinceLastSession
  const bNeglect = b.daysSinceLastSession === null ? Number.POSITIVE_INFINITY : b.daysSinceLastSession
  if (aNeglect !== bNeglect) return bNeglect - aNeglect

  // 3. Plus grand manque a l'objectif du jour d'abord.
  const aShortfall = a.goalSeconds - a.secondsToday
  const bShortfall = b.goalSeconds - b.secondsToday
  if (aShortfall !== bShortfall) return bShortfall - aShortfall

  // 4. Score de regularite le plus bas d'abord.
  if (a.regularityScore !== b.regularityScore) return a.regularityScore - b.regularityScore

  // 5. Ordre de creation, pour un resultat deterministe.
  return a.account.createdAt.localeCompare(b.account.createdAt)
}

/**
 * Ordonne les comptes par ordre de priorite d'attention decroissante : celui
 * qui a le plus besoin d'etre travaille en premier. Voir compareEntries pour
 * l'ordre exact des criteres de depart.
 */
export function nextUp (accounts: Account[], stats: StatsFile, today: Date): PilotEntry[] {
  return accounts
    .map(account => pilotEntryFor(account, stats, today))
    .sort(compareEntries)
}
