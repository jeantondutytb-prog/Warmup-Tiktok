import { describe, it, expect } from 'vitest'
import { regularityScore, nextUp, pilotEntryFor, WINDOW_DAYS } from '../src/core/pilot'
import { emptyStats, addSeconds, dayKey } from '../src/core/stats'
import type { Account, StatsFile } from '../src/core/types'

// Jour de reference pour tous les tests : jeudi 20 aout 2026.
const TODAY = new Date(2026, 7, 20)

let nextAccountSeq = 0

function makeAccount (overrides: Partial<Account> = {}): Account {
  nextAccountSeq += 1
  return {
    id: `acc-${nextAccountSeq}`,
    label: `@compte-${nextAccountSeq}`,
    partition: `persist:tt-acc-${nextAccountSeq}`,
    proxy: null,
    userAgent: null,
    notes: '',
    dailyGoalMinutes: 15,
    createdAt: daysBefore(TODAY, 30).toISOString(),
    ...overrides
  }
}

/** Date locale a `n` jours avant `base`, a midi pour eviter tout effet de fuseau au moment du round-trip ISO. */
function daysBefore (base: Date, n: number): Date {
  return new Date(base.getFullYear(), base.getMonth(), base.getDate() - n, 12)
}

/** Ajoute `seconds` au jour situe `n` jours avant TODAY, pour `accountId`. */
function withSecondsNDaysAgo (stats: StatsFile, accountId: string, n: number, seconds: number): StatsFile {
  return addSeconds(stats, dayKey(daysBefore(TODAY, n)), accountId, seconds)
}

describe('regularityScore', () => {
  it('vaut 0 pour un compte sans aucun historique', () => {
    // attendance=0, attainment=0 (aucun jour actif), gapPenalty=min(1,14/14)=1
    // raw = 0.55*0 + 0.45*0 - 0.25*1 = -0.25, clampe a 0 -> score 0 quelle que soit la maturite.
    const account = makeAccount()
    expect(regularityScore(account, emptyStats(), TODAY)).toBe(0)
  })

  it('vaut 100 pour 14/14 jours actifs a l objectif plein, compte mature', () => {
    // attendance=1, attainment=1 (chaque jour min(1,ratio)=1), gapPenalty=0
    // raw = 0.55*1 + 0.45*1 - 0.25*0 = 1, clampe a 1, maturity=1 (cree 30j avant) -> 100*1*1=100
    let stats = emptyStats()
    const account = makeAccount({ dailyGoalMinutes: 15 })
    for (let n = 0; n < WINDOW_DAYS; n++) {
      stats = withSecondsNDaysAgo(stats, account.id, n, 15 * 60)
    }
    expect(regularityScore(account, stats, TODAY)).toBe(100)
  })

  it('vaut 78 pour 14/14 jours actifs a la moitie de l objectif, compte mature', () => {
    // attendance=1, attainment=0.5 (chaque jour min(1,0.5)=0.5), gapPenalty=0
    // raw = 0.55*1 + 0.45*0.5 - 0 = 0.775, clampe a 0.775, maturity=1 -> round(100*0.775)=round(77.5)=78
    let stats = emptyStats()
    const account = makeAccount({ dailyGoalMinutes: 15 })
    for (let n = 0; n < WINDOW_DAYS; n++) {
      stats = withSecondsNDaysAgo(stats, account.id, n, (15 * 60) / 2)
    }
    expect(regularityScore(account, stats, TODAY)).toBe(78)
  })

  it('separe jours actifs regroupes et jours actifs repartis a attendance et attainment egales', () => {
    // Les deux comptes ont 7 jours actifs sur 14, tous a l objectif plein :
    // attendance=0.5 et attainment=1 identiques pour les deux. Seul gapPenalty differe.
    const goalMinutes = 15
    let clustered = emptyStats()
    const clusteredAccount = makeAccount({ dailyGoalMinutes: goalMinutes })
    // Actif les 7 jours les plus recents (n=0..6) -> la plus longue coupure regroupe
    // les 7 jours les plus anciens : longestGap=7, gapPenalty=min(1,7/14)=0.5
    // raw = 0.55*0.5 + 0.45*1 - 0.25*0.5 = 0.275+0.45-0.125=0.6 -> score 60
    for (let n = 0; n <= 6; n++) {
      clustered = withSecondsNDaysAgo(clustered, clusteredAccount.id, n, goalMinutes * 60)
    }

    let spread = emptyStats()
    const spreadAccount = makeAccount({ dailyGoalMinutes: goalMinutes })
    // Actif un jour sur deux (n=0,2,4,6,8,10,12) -> chaque coupure fait 1 jour :
    // longestGap=1, gapPenalty=min(1,1/14)=0.0714...
    // raw = 0.55*0.5 + 0.45*1 - 0.25*0.0714... = 0.275+0.45-0.017857=0.707142...
    // -> round(100*0.707142...) = round(70.71...) = 71
    for (let n = 0; n <= 12; n += 2) {
      spread = withSecondsNDaysAgo(spread, spreadAccount.id, n, goalMinutes * 60)
    }

    const clusteredScore = regularityScore(clusteredAccount, clustered, TODAY)
    const spreadScore = regularityScore(spreadAccount, spread, TODAY)
    expect(clusteredScore).toBe(60)
    expect(spreadScore).toBe(71)
    expect(spreadScore).toBeGreaterThan(clusteredScore)
  })

  it('plafonne un compte cree la veille meme avec un jour actif a l objectif', () => {
    // Compte cree 1 jour avant TODAY, actif aujourd'hui a l objectif plein.
    // attendance=1/14, attainment=1 (le seul jour actif est a l objectif),
    // longestGap=13 (les 13 jours precedents, avant la creation, sont inactifs),
    // gapPenalty=min(1,13/14)=0.928571...
    // raw = 0.55*(1/14) + 0.45*1 - 0.25*0.928571... = 0.039286+0.45-0.232143=0.257143...
    // maturity = min(1, 1/14) = 0.071428...  (cree il y a 1 jour seulement)
    // score = round(100 * 0.071428... * 0.257143...) = round(1.8367...) = 2
    let stats = emptyStats()
    const account = makeAccount({ dailyGoalMinutes: 15, createdAt: daysBefore(TODAY, 1).toISOString() })
    stats = addSeconds(stats, dayKey(TODAY), account.id, 15 * 60)
    expect(regularityScore(account, stats, TODAY)).toBe(2)
  })

  it('la meme activite avec un compte mature donne un score bien plus haut (verifie l effet du plafond de maturite)', () => {
    // Meme raw=0.257143... que le test precedent mais maturity=1 (cree 30j avant)
    // -> round(100*1*0.257143...) = round(25.71...) = 26, tres au-dessus du 2 du compte de 2 jours.
    let stats = emptyStats()
    const account = makeAccount({ dailyGoalMinutes: 15, createdAt: daysBefore(TODAY, 30).toISOString() })
    stats = addSeconds(stats, dayKey(TODAY), account.id, 15 * 60)
    expect(regularityScore(account, stats, TODAY)).toBe(26)
  })

  it('une session exactement au bord le plus ancien de la fenetre (13 jours avant TODAY) compte', () => {
    // WINDOW_DAYS=14 jours se terminant sur TODAY inclus => le jour le plus ancien
    // de la fenetre est TODAY - 13 jours (offset -13), PAS TODAY - 14 jours.
    // Une seule session, 13 jours avant TODAY, a l objectif plein :
    // attendance=1/14, attainment=1, longestGap=13, gapPenalty=13/14
    // -> meme calcul que le test de plafond de maturite ci-dessus, avec un compte mature -> score 26.
    let stats = emptyStats()
    const account = makeAccount({ dailyGoalMinutes: 15 })
    stats = withSecondsNDaysAgo(stats, account.id, 13, 15 * 60)
    expect(regularityScore(account, stats, TODAY)).toBe(26)
  })

  it('une session 14 jours avant TODAY tombe hors fenetre et ne compte pas', () => {
    // D apres la definition formelle ("WINDOW = 14 jours se terminant sur le jour donne
    // inclus"), la fenetre couvre TODAY-13 .. TODAY (14 jours). Une session TODAY-14
    // est donc hors fenetre : aucun jour actif dans la fenetre -> meme resultat que
    // "aucun historique" -> score 0.
    // ATTENTION (a signaler, pas a corriger silencieusement) : l enonce de la tache
    // decrit cette limite comme "une session il y a exactement 14 jours compte, 15
    // jours ne compte pas", ce qui correspondrait a une fenetre de 15 jours et
    // contredit "WINDOW = 14 jours" tel que defini plus haut dans le meme enonce.
    // Ce test suit la definition formelle (WINDOW=14, bord a 13 jours), pas la
    // description litterale du cas limite.
    let stats = emptyStats()
    const account = makeAccount({ dailyGoalMinutes: 15 })
    stats = withSecondsNDaysAgo(stats, account.id, 14, 15 * 60)
    expect(regularityScore(account, stats, TODAY)).toBe(0)
  })
})

describe('pilotEntryFor', () => {
  it('expose secondsToday, goalSeconds et daysSinceLastSession=null quand le compte n a jamais ete actif', () => {
    const account = makeAccount({ dailyGoalMinutes: 20 })
    const entry = pilotEntryFor(account, emptyStats(), TODAY)
    expect(entry.account).toBe(account)
    expect(entry.secondsToday).toBe(0)
    expect(entry.goalSeconds).toBe(20 * 60)
    expect(entry.daysSinceLastSession).toBeNull()
    expect(entry.regularityScore).toBe(0)
  })

  it('calcule daysSinceLastSession a partir de la derniere session avec activite, meme hors fenetre de score', () => {
    let stats = emptyStats()
    const account = makeAccount()
    stats = withSecondsNDaysAgo(stats, account.id, 40, 300)
    const entry = pilotEntryFor(account, stats, TODAY)
    expect(entry.daysSinceLastSession).toBe(40)
  })
})

describe('nextUp', () => {
  it('place en dernier un compte ayant deja atteint l objectif du jour', () => {
    let stats = emptyStats()
    const met = makeAccount({ dailyGoalMinutes: 10 })
    const unmet = makeAccount({ dailyGoalMinutes: 10 })
    // Meme negligence (0 jour, actifs aujourd'hui tous les deux) : seul l atteinte
    // de l objectif differe.
    stats = addSeconds(stats, dayKey(TODAY), met.id, 10 * 60)
    stats = addSeconds(stats, dayKey(TODAY), unmet.id, 10 * 60 - 1)
    const order = nextUp([met, unmet], stats, TODAY).map(e => e.account.id)
    expect(order).toEqual([unmet.id, met.id])
  })

  it('place en premier un compte jamais travaille', () => {
    let stats = emptyStats()
    const worked = makeAccount({ dailyGoalMinutes: 10 })
    const neverWorked = makeAccount({ dailyGoalMinutes: 10 })
    // worked a une session ancienne mais reelle ; neverWorked n en a aucune.
    // Aucun des deux n a atteint l objectif aujourd'hui (0 seconde aujourd'hui).
    stats = withSecondsNDaysAgo(stats, worked.id, 3, 5)
    const order = nextUp([worked, neverWorked], stats, TODAY).map(e => e.account.id)
    expect(order).toEqual([neverWorked.id, worked.id])
  })

  it('isole le critere 1 (objectif atteint) : neglect, manque et score egaux par ailleurs', () => {
    let stats = emptyStats()
    const met = makeAccount({ dailyGoalMinutes: 10 })
    const unmet = makeAccount({ dailyGoalMinutes: 10 })
    stats = addSeconds(stats, dayKey(TODAY), met.id, 10 * 60)
    stats = addSeconds(stats, dayKey(TODAY), unmet.id, 10 * 60 - 1)
    const order = nextUp([met, unmet], stats, TODAY).map(e => e.account.id)
    expect(order).toEqual([unmet.id, met.id])
  })

  it('isole le critere 2 (negligence) : objectif non atteint et score egaux (0) pour les deux, seule la negligence differe', () => {
    let stats = emptyStats()
    const lessNeglected = makeAccount({ dailyGoalMinutes: 10 })
    const moreNeglected = makeAccount({ dailyGoalMinutes: 10 })
    // Les deux dernieres sessions sont hors de la fenetre de score (>13 jours),
    // donc regularityScore=0 pour les deux ; aucune activite aujourd'hui donc
    // meme manque (shortfall) pour les deux.
    stats = withSecondsNDaysAgo(stats, lessNeglected.id, 20, 5)
    stats = withSecondsNDaysAgo(stats, moreNeglected.id, 40, 5)
    const order = nextUp([lessNeglected, moreNeglected], stats, TODAY).map(e => e.account.id)
    expect(order).toEqual([moreNeglected.id, lessNeglected.id])
  })

  it('isole le critere 3 (manque a l objectif) : negligence et score egaux (jamais travaille, score 0), seul l objectif differe', () => {
    const smallGoal = makeAccount({ dailyGoalMinutes: 10 })
    const bigGoal = makeAccount({ dailyGoalMinutes: 20 })
    // Aucune activite du tout pour les deux : daysSinceLastSession=null (egal),
    // regularityScore=0 (egal). shortfall = goalSeconds - 0 = goalSeconds, donc
    // bigGoal (1200s) > smallGoal (600s).
    const order = nextUp([smallGoal, bigGoal], emptyStats(), TODAY).map(e => e.account.id)
    expect(order).toEqual([bigGoal.id, smallGoal.id])
  })

  it('isole le critere 4 (score de regularite) : negligence et manque egaux, seul le score differe', () => {
    let stats = emptyStats()
    const lowerScore = makeAccount({ dailyGoalMinutes: 15 })
    const higherScore = makeAccount({ dailyGoalMinutes: 15 })
    // Pour les deux, la derniere session active est il y a 5 jours (offset commun),
    // donc daysSinceLastSession=5 pour les deux, et aucune activite aujourd'hui
    // donc meme shortfall pour les deux.
    // lowerScore : une seule session, 5 jours avant TODAY, a l objectif plein -> score 35
    //   (attendance=1/14, attainment=1, longestGap=8 -> gapPenalty=8/14=0.5714...
    //    raw=0.55/14+0.45-0.25*0.5714...=0.039286+0.45-0.142857=0.346428...
    //    round(100*0.346428...)=35)
    // higherScore : meme session 5 jours avant + 2 sessions supplementaires plus
    //   anciennes (13 et 12 jours avant TODAY), toutes a l objectif plein, sans
    //   toucher au jour le plus recent actif (toujours 5 jours avant) -> score 46
    //   (attendance=3/14, attainment=1, longestGap=6 -> gapPenalty=6/14=0.42857...
    //    raw=0.55*3/14+0.45-0.25*0.42857...=0.117857+0.45-0.107143=0.460714...
    //    round(100*0.460714...)=46)
    stats = withSecondsNDaysAgo(stats, lowerScore.id, 5, 15 * 60)
    stats = withSecondsNDaysAgo(stats, higherScore.id, 5, 15 * 60)
    stats = withSecondsNDaysAgo(stats, higherScore.id, 13, 15 * 60)
    stats = withSecondsNDaysAgo(stats, higherScore.id, 12, 15 * 60)

    const lowerActual = regularityScore(lowerScore, stats, TODAY)
    const higherActual = regularityScore(higherScore, stats, TODAY)
    expect(lowerActual).toBe(35)
    expect(higherActual).toBe(46)

    const order = nextUp([higherScore, lowerScore], stats, TODAY).map(e => e.account.id)
    expect(order).toEqual([lowerScore.id, higherScore.id])
  })

  it('isole le critere 5 (ordre de creation) : negligence, manque et score tous egaux (0), seule la date de creation differe', () => {
    const createdLater = makeAccount({ dailyGoalMinutes: 10, createdAt: daysBefore(TODAY, 5).toISOString() })
    const createdEarlier = makeAccount({ dailyGoalMinutes: 10, createdAt: daysBefore(TODAY, 60).toISOString() })
    // Aucune activite pour les deux : negligence=null, shortfall=600s, score=0 pour
    // les deux (score=0 des qu il n y a aucun jour actif, quelle que soit la maturite,
    // car raw se clampe a 0 avant d etre multiplie par maturity).
    const order = nextUp([createdLater, createdEarlier], emptyStats(), TODAY).map(e => e.account.id)
    expect(order).toEqual([createdEarlier.id, createdLater.id])
  })
})
