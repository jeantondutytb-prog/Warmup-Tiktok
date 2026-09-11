import { describe, it, expect, beforeEach, afterEach } from 'vitest'
import { mkdtemp, rm, writeFile, readdir } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { readJson, writeJsonAtomic } from '../src/main/storage'

let dir: string

beforeEach(async () => {
  dir = await mkdtemp(join(tmpdir(), 'tcc-'))
})

afterEach(async () => {
  await rm(dir, { recursive: true, force: true })
})

describe('readJson', () => {
  it('renvoie la valeur de repli si le fichier n existe pas', async () => {
    const result = await readJson(join(dir, 'absent.json'), { version: 1 })
    expect(result).toEqual({ version: 1 })
  })

  it('renvoie la valeur de repli si le fichier est corrompu', async () => {
    const path = join(dir, 'casse.json')
    await writeFile(path, '{ ceci n est pas du json')
    expect(await readJson(path, { version: 1 })).toEqual({ version: 1 })
  })

  it('relit ce qui a ete ecrit', async () => {
    const path = join(dir, 'ok.json')
    await writeJsonAtomic(path, { version: 1, accounts: ['a'] })
    expect(await readJson(path, null)).toEqual({ version: 1, accounts: ['a'] })
  })
})

describe('writeJsonAtomic', () => {
  it('cree les dossiers parents manquants', async () => {
    const path = join(dir, 'imbrique', 'profond', 'data.json')
    await writeJsonAtomic(path, { ok: true })
    expect(await readJson(path, null)).toEqual({ ok: true })
  })

  it('ne laisse aucun fichier temporaire derriere lui', async () => {
    await writeJsonAtomic(join(dir, 'data.json'), { ok: true })
    expect(await readdir(dir)).toEqual(['data.json'])
  })

  it('remplace le contenu precedent', async () => {
    const path = join(dir, 'data.json')
    await writeJsonAtomic(path, { valeur: 1 })
    await writeJsonAtomic(path, { valeur: 2 })
    expect(await readJson(path, null)).toEqual({ valeur: 2 })
  })

  it('laisse le fichier precedent intact quand l ecriture echoue', async () => {
    const path = join(dir, 'data.json')
    await writeJsonAtomic(path, { valeur: 1 })

    // Create circular reference that JSON.stringify cannot serialize
    const circularObj: any = { valeur: 2 }
    circularObj.self = circularObj

    await expect(writeJsonAtomic(path, circularObj)).rejects.toThrow()

    // Original file should still be intact
    expect(await readJson(path, null)).toEqual({ valeur: 1 })
  })

  it('ne laisse aucun fichier temporaire derriere lui en cas d erreur', async () => {
    const path = join(dir, 'data.json')
    await writeJsonAtomic(path, { valeur: 1 })

    // Create circular reference that JSON.stringify cannot serialize
    const circularObj: any = { valeur: 2 }
    circularObj.self = circularObj

    try {
      await writeJsonAtomic(path, circularObj)
    } catch {
      // Expected to fail
    }

    // Directory should contain only the target file, no .tmp files
    const files = await readdir(dir)
    expect(files).toEqual(['data.json'])
  })

  it('les ecritures concurrentes au meme chemin ne corrompent pas le fichier', async () => {
    const path = join(dir, 'data.json')

    // Fire multiple writes without awaiting
    const promises = [
      writeJsonAtomic(path, { valeur: 1 }),
      writeJsonAtomic(path, { valeur: 2 }),
      writeJsonAtomic(path, { valeur: 3 })
    ]

    await Promise.all(promises)

    // File should contain valid JSON and match one of the written values
    const result = await readJson(path, null)
    expect(result).toBeDefined()
    expect([
      { valeur: 1 },
      { valeur: 2 },
      { valeur: 3 }
    ]).toContainEqual(result)

    // No .tmp files should remain
    const files = await readdir(dir)
    expect(files).toEqual(['data.json'])
  })

  it('une ecriture reussie apres une echec n est pas empoisonnee', async () => {
    const path = join(dir, 'data.json')
    await writeJsonAtomic(path, { initial: true })

    // Create circular reference that JSON.stringify cannot serialize
    const circularObj: any = { fail: true }
    circularObj.self = circularObj

    // Issue write A (will fail) WITHOUT awaiting - leaves it pending
    const failing = writeJsonAtomic(path, circularObj)

    // Issue write B WHILE A is pending - chains onto A's rejecting promise
    const ok = writeJsonAtomic(path, { valeur: 42 })

    // Now await both and verify: A rejects, B still succeeds
    await expect(failing).rejects.toThrow()
    await expect(ok).resolves.toBeUndefined()

    // Data from write B should be on disk
    expect(await readJson(path, null)).toEqual({ valeur: 42 })
  })

  it('l ordre d emission des ecritures est respecte', async () => {
    const path = join(dir, 'data.json')

    // Issue writes without awaiting - they should be ordered by issuance
    const promises = [
      writeJsonAtomic(path, { order: 1 }),
      writeJsonAtomic(path, { order: 2 }),
      writeJsonAtomic(path, { order: 3 }),
      writeJsonAtomic(path, { order: 4 })
    ]

    await Promise.all(promises)

    // Final content should be the LAST value issued, not any previous one
    const result = await readJson(path, null)
    expect(result).toEqual({ order: 4 })

    // No .tmp files should remain
    const files = await readdir(dir)
    expect(files).toEqual(['data.json'])
  })

})
