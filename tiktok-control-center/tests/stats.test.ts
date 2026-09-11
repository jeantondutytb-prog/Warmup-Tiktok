import { describe, it, expect } from 'vitest'
import { emptyStats, addSeconds, secondsFor, purgeOlderThan, dayKey, migrateStats } from '../src/core/stats'

describe('dayKey', () => {
  it('formate une date en AAAA-MM-JJ local', () => {
    expect(dayKey(new Date(2026, 7, 6, 14, 30))).toBe('2026-08-06')
  })

  it('complete les mois et jours a un chiffre', () => {
    expect(dayKey(new Date(2026, 0, 3, 9, 0))).toBe('2026-01-03')
  })
})

describe('addSeconds', () => {
  it('cree le jour et le compte au premier ajout', () => {
    const next = addSeconds(emptyStats(), '2026-08-06', 'a1', 5)
    expect(secondsFor(next, '2026-08-06', 'a1')).toBe(5)
  })

  it('cumule les ajouts successifs', () => {
    let stats = emptyStats()
    stats = addSeconds(stats, '2026-08-06', 'a1', 5)
    stats = addSeconds(stats, '2026-08-06', 'a1', 7)
    expect(secondsFor(stats, '2026-08-06', 'a1')).toBe(12)
  })

  it('garde les comptes independants', () => {
    let stats = emptyStats()
    stats = addSeconds(stats, '2026-08-06', 'a1', 5)
    stats = addSeconds(stats, '2026-08-06', 'b2', 9)
    expect(secondsFor(stats, '2026-08-06', 'a1')).toBe(5)
    expect(secondsFor(stats, '2026-08-06', 'b2')).toBe(9)
  })

  it('garde les jours independants', () => {
    let stats = emptyStats()
    stats = addSeconds(stats, '2026-08-06', 'a1', 5)
    stats = addSeconds(stats, '2026-08-07', 'a1', 3)
    expect(secondsFor(stats, '2026-08-06', 'a1')).toBe(5)
    expect(secondsFor(stats, '2026-08-07', 'a1')).toBe(3)
  })

  it('ne modifie pas l objet source', () => {
    const original = emptyStats()
    addSeconds(original, '2026-08-06', 'a1', 5)
    expect(original.days).toEqual({})
  })
})

describe('secondsFor', () => {
  it('renvoie zero pour un jour inconnu', () => {
    expect(secondsFor(emptyStats(), '2026-08-06', 'a1')).toBe(0)
  })

  it('renvoie zero pour un compte inconnu dans un jour connu', () => {
    const stats = addSeconds(emptyStats(), '2026-08-06', 'a1', 5)
    expect(secondsFor(stats, '2026-08-06', 'inconnu')).toBe(0)
  })
})

describe('purgeOlderThan', () => {
  it('supprime les jours strictement anterieurs au seuil', () => {
    let stats = emptyStats()
    stats = addSeconds(stats, '2026-05-01', 'a1', 5)
    stats = addSeconds(stats, '2026-08-06', 'a1', 5)
    const purged = purgeOlderThan(stats, '2026-08-01')
    expect(Object.keys(purged.days)).toEqual(['2026-08-06'])
  })

  it('conserve le jour seuil lui-meme', () => {
    const stats = addSeconds(emptyStats(), '2026-08-01', 'a1', 5)
    expect(Object.keys(purgeOlderThan(stats, '2026-08-01').days)).toEqual(['2026-08-01'])
  })
})

describe('migrateStats', () => {
  it('renvoie un fichier vide pour null', () => {
    expect(migrateStats(null)).toEqual(emptyStats())
  })

  it('renvoie un fichier vide pour une chaine', () => {
    expect(migrateStats('pas un objet')).toEqual(emptyStats())
  })

  it('renvoie un fichier vide pour un objet vide', () => {
    expect(migrateStats({})).toEqual(emptyStats())
  })

  it('renvoie un fichier vide pour une version incorrecte', () => {
    expect(migrateStats({ version: 2, days: {} })).toEqual(emptyStats())
  })

  it('renvoie un fichier vide quand days est absent', () => {
    expect(migrateStats({ version: 1 })).toEqual(emptyStats())
  })

  it('renvoie un fichier vide quand days est un tableau', () => {
    expect(migrateStats({ version: 1, days: [] })).toEqual(emptyStats())
  })

  it('ignore un jour dont la valeur est une chaine', () => {
    const result = migrateStats({ version: 1, days: { '2026-08-06': 'pas un objet' } })
    expect(result).toEqual({ version: 1, days: {} })
  })

  it('ignore un jour dont la valeur est un tableau', () => {
    const result = migrateStats({ version: 1, days: { '2026-08-06': [] } })
    expect(result).toEqual({ version: 1, days: {} })
  })

  it('ignore un compte dont les secondes sont NaN', () => {
    const result = migrateStats({ version: 1, days: { '2026-08-06': { a1: NaN } } })
    expect(result).toEqual({ version: 1, days: { '2026-08-06': {} } })
  })

  it('ignore un compte dont les secondes sont une chaine', () => {
    const result = migrateStats({ version: 1, days: { '2026-08-06': { a1: '5' } } })
    expect(result).toEqual({ version: 1, days: { '2026-08-06': {} } })
  })

  it('conserve les comptes valides et ecarte les malformes dans le meme jour', () => {
    const result = migrateStats({
      version: 1,
      days: { '2026-08-06': { a1: 12, a2: 'nope', a3: Infinity } }
    })
    expect(result).toEqual({ version: 1, days: { '2026-08-06': { a1: 12 } } })
  })

  it('laisse passer un fichier valide inchange', () => {
    const valid = { version: 1, days: { '2026-08-06': { a1: 5, a2: 9 } } }
    expect(migrateStats(valid)).toEqual(valid)
  })
})
