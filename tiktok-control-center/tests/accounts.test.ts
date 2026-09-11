import { describe, it, expect } from 'vitest'
import {
  emptyAccounts, createAccount, updateAccount, deleteAccount,
  migrate, partitionFor, pageOf
} from '../src/core/accounts'

const input = { id: 'a1', label: '@niche', createdAt: '2026-08-06T12:00:00Z' }

describe('partitionFor', () => {
  it('prefixe l identifiant pour obtenir une partition persistante', () => {
    expect(partitionFor('a1')).toBe('persist:tt-a1')
  })
})

describe('createAccount', () => {
  it('ajoute un compte avec ses valeurs par defaut', () => {
    const file = createAccount(emptyAccounts(), input)
    expect(file.accounts).toHaveLength(1)
    expect(file.accounts[0]).toEqual({
      id: 'a1',
      label: '@niche',
      partition: 'persist:tt-a1',
      proxy: null,
      userAgent: null,
      notes: '',
      dailyGoalMinutes: 15,
      createdAt: '2026-08-06T12:00:00Z'
    })
  })

  it('ajoute a la fin de la liste', () => {
    let file = createAccount(emptyAccounts(), input)
    file = createAccount(file, { ...input, id: 'b2', label: '@autre' })
    expect(file.accounts.map(a => a.id)).toEqual(['a1', 'b2'])
  })

  it('refuse un identifiant deja utilise', () => {
    const file = createAccount(emptyAccounts(), input)
    expect(() => createAccount(file, input)).toThrow('identifiant deja utilise')
  })

  it('ne modifie pas l objet source', () => {
    const original = emptyAccounts()
    createAccount(original, input)
    expect(original.accounts).toEqual([])
  })
})

describe('updateAccount', () => {
  it('applique un patch partiel', () => {
    const file = updateAccount(createAccount(emptyAccounts(), input), 'a1', { notes: 'cuisine' })
    expect(file.accounts[0].notes).toBe('cuisine')
    expect(file.accounts[0].label).toBe('@niche')
  })

  it('accepte un proxy', () => {
    const file = updateAccount(createAccount(emptyAccounts(), input), 'a1', {
      proxy: { server: 'http://proxy.example:8080' }
    })
    expect(file.accounts[0].proxy).toEqual({ server: 'http://proxy.example:8080' })
  })

  it('refuse de changer l identifiant ou la partition', () => {
    const file = createAccount(emptyAccounts(), input)
    // @ts-expect-error on verifie la protection a l execution
    expect(() => updateAccount(file, 'a1', { id: 'autre' })).toThrow('champ immuable')
    // @ts-expect-error on verifie la protection a l execution
    expect(() => updateAccount(file, 'a1', { partition: 'persist:x' })).toThrow('champ immuable')
  })

  it('leve une erreur si le compte n existe pas', () => {
    expect(() => updateAccount(emptyAccounts(), 'inconnu', { notes: 'x' })).toThrow('compte introuvable')
  })
})

describe('deleteAccount', () => {
  it('retire le compte demande', () => {
    let file = createAccount(emptyAccounts(), input)
    file = createAccount(file, { ...input, id: 'b2', label: '@autre' })
    expect(deleteAccount(file, 'a1').accounts.map(a => a.id)).toEqual(['b2'])
  })

  it('leve une erreur si le compte n existe pas', () => {
    expect(() => deleteAccount(emptyAccounts(), 'inconnu')).toThrow('compte introuvable')
  })
})

describe('migrate', () => {
  it('renvoie un fichier vide pour une entree nulle ou invalide', () => {
    expect(migrate(null)).toEqual(emptyAccounts())
    expect(migrate('nawak')).toEqual(emptyAccounts())
    expect(migrate({ version: 99 })).toEqual(emptyAccounts())
  })

  it('conserve un fichier valide', () => {
    const file = createAccount(emptyAccounts(), input)
    expect(migrate(file)).toEqual(file)
  })

  it('complete les champs manquants d un compte partiel', () => {
    const raw = { version: 1, accounts: [{ id: 'a1', label: '@niche' }] }
    const account = migrate(raw).accounts[0]
    expect(account.partition).toBe('persist:tt-a1')
    expect(account.proxy).toBeNull()
    expect(account.notes).toBe('')
    expect(account.dailyGoalMinutes).toBe(15)
  })

  it('ecarte les entrees sans identifiant', () => {
    const raw = { version: 1, accounts: [{ label: 'sans id' }, { id: 'a1', label: 'ok' }] }
    expect(migrate(raw).accounts.map(a => a.id)).toEqual(['a1'])
  })

  it('normalise proxy lorsqu il est une string', () => {
    const raw = { version: 1, accounts: [{ id: 'a1', label: 'test', proxy: 'http://host:8080' }] }
    const account = migrate(raw).accounts[0]
    expect(account.proxy).toBeNull()
  })

  it('accepte proxy valide avec server et credentials', () => {
    const raw = {
      version: 1,
      accounts: [{
        id: 'a1',
        label: 'test',
        proxy: { server: 'http://proxy.example:8080', username: 'user', password: 'pass' }
      }]
    }
    const account = migrate(raw).accounts[0]
    expect(account.proxy).toEqual({ server: 'http://proxy.example:8080', username: 'user', password: 'pass' })
  })

  it('normalise proxy sans server a null', () => {
    const raw = { version: 1, accounts: [{ id: 'a1', label: 'test', proxy: { username: 'user' } }] }
    const account = migrate(raw).accounts[0]
    expect(account.proxy).toBeNull()
  })

  it('normalise proxy avec server non-string a null', () => {
    const raw = { version: 1, accounts: [{ id: 'a1', label: 'test', proxy: { server: 123 } }] }
    const account = migrate(raw).accounts[0]
    expect(account.proxy).toBeNull()
  })

  it('garde le premier compte en cas d identifiants dupliques', () => {
    const raw = {
      version: 1,
      accounts: [
        { id: 'a1', label: 'premier' },
        { id: 'a1', label: 'doublon' }
      ]
    }
    const result = migrate(raw)
    expect(result.accounts).toHaveLength(1)
    expect(result.accounts[0].label).toBe('premier')
  })
})

describe('pageOf', () => {
  const many = Array.from({ length: 8 }, (_, i) => ({ ...input, id: `id${i}` }))
    .reduce((file, a) => createAccount(file, a), emptyAccounts()).accounts

  it('renvoie les six premiers comptes en page zero', () => {
    expect(pageOf(many, 0).map(a => a.id)).toEqual(['id0', 'id1', 'id2', 'id3', 'id4', 'id5'])
  })

  it('renvoie le reste en page un', () => {
    expect(pageOf(many, 1).map(a => a.id)).toEqual(['id6', 'id7'])
  })

  it('renvoie une liste vide au-dela de la derniere page', () => {
    expect(pageOf(many, 5)).toEqual([])
  })
})
