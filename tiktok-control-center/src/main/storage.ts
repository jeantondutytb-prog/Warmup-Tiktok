import { readFile, writeFile, rename, mkdir, unlink } from 'node:fs/promises'
import { dirname, join, basename, resolve } from 'node:path'

/** Lit un JSON. Un fichier absent ou illisible retombe sur `fallback` plutot que de lever. */
export async function readJson<T> (path: string, fallback: T): Promise<T> {
  try {
    return JSON.parse(await readFile(path, 'utf8')) as T
  } catch {
    return fallback
  }
}

// Module-level counter for unique temp filenames per call
let writeCounter = 0

// Map to serialize writes per target path, preventing renames from landing out of order
const writePromises = new Map<string, Promise<void>>()

/**
 * Ecrit un JSON en deux temps : fichier temporaire puis `rename`. Le `rename`
 * etant atomique sur un meme volume, une coupure en cours d'ecriture laisse
 * l'ancien fichier intact au lieu d'un fichier tronque.
 */
export function writeJsonAtomic (path: string, data: unknown): Promise<void> {
  const resolvedPath = resolve(path)

  // Get the previous promise for this path
  const previous = writePromises.get(resolvedPath) ?? Promise.resolve()

  // Build the chain: neutralize previous failures, then lazily perform this write
  const run = previous
    .catch(() => {})                                    // previous failing must not block or infect us
    .then(() => performWrite(resolvedPath, data))      // lazy: starts only after previous settles

  writePromises.set(resolvedPath, run)

  // Clean up map entry when this write settles, but only if no newer call has replaced it
  void run.catch(() => {}).finally(() => {
    if (writePromises.get(resolvedPath) === run) {
      writePromises.delete(resolvedPath)
    }
  })

  return run
}

async function performWrite (path: string, data: unknown): Promise<void> {
  const dir = dirname(path)
  await mkdir(dir, { recursive: true })
  const tmp = join(dir, `.${basename(path)}.${process.pid}.${writeCounter++}.tmp`)
  try {
    await writeFile(tmp, JSON.stringify(data, null, 2), 'utf8')
    await rename(tmp, path)
  } catch (error) {
    await unlink(tmp).catch(() => {})
    throw error
  }
}
