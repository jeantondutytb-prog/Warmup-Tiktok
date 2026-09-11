function escapeRegExp (value: string): string {
  return value.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
}

/**
 * Retire du user-agent les jetons ajoutes par Electron : `Electron/<version>`
 * et `<nom-app>/<version>`. Ce qui reste est le user-agent Chrome authentique
 * du Chromium embarque — donc toujours coherent avec la version reelle du
 * moteur, contrairement a une chaine ecrite en dur qui se perimerait.
 */
export function stripElectronTokens (ua: string, appName: string): string {
  return ua
    .replace(/\s?Electron\/\S+/, '')
    .replace(new RegExp(`\\s?${escapeRegExp(appName)}\\/\\S+`), '')
    .replace(/\s{2,}/g, ' ')
    .trim()
}

// Utilisee uniquement si `desktopUa` ne contient aucun jeton `Chrome/<version>`
// — normalement impossible puisque Electron embarque toujours Chromium, donc
// ce cas ne devrait jamais se produire en pratique. Elle existe pour eviter
// de produire un user-agent absurde du genre `Chrome/undefined` si jamais un
// appelant passe une chaine inattendue (ex. tests, UA deja modifie a la main).
// La valeur n'a pas vocation a rester exacte dans le temps : contrairement au
// chemin normal (qui recopie la version reelle du Chromium embarque), un
// repli fige finira par se perimer. C'est un compromis assume : mieux vaut un
// numero de version plausible mais legerement date que "undefined" dans un
// user-agent envoye a un site tiers.
const FALLBACK_CHROME_VERSION = '124.0.0.0'

/**
 * Derive un user-agent mobile (Android Chrome) a partir d'un user-agent
 * desktop Chrome authentique — typiquement la sortie de stripElectronTokens.
 * La version Chrome annoncee est extraite du user-agent fourni plutot
 * qu'ecrite en dur, pour la meme raison que stripElectronTokens : elle reste
 * automatiquement coherente avec le Chromium reellement embarque par
 * Electron, sans perimer avec le temps.
 */
export function toMobileUserAgent (desktopUa: string): string {
  const match = /Chrome\/(\S+)/.exec(desktopUa)
  const version = match?.[1] ?? FALLBACK_CHROME_VERSION
  return `Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/${version} Mobile Safari/537.36`
}
