/**
 * Classification pure des destinations qu'une vue de compte a le droit
 * d'atteindre. TikTok est un site tiers que nous ne controlons pas : sa page
 * peut a tout moment tenter de rediriger la vue vers un schema non web (ex.
 * `itms-apps:` pour ouvrir l'App Store), d'ouvrir une fenetre, ou de naviguer
 * hors de son propre domaine. Ces fonctions repondent uniquement a "cette
 * destination est-elle autorisee ?" ; c'est ViewManager (src/main) qui les
 * branche sur les evenements Electron (will-navigate, setWindowOpenHandler).
 *
 * Isolees ici (electron-free) pour rester testables sans lancer Electron.
 */

/** Seuls ces deux schemas restent dans l'application ; tout le reste (custom
 *  schemes, `mailto:`, `tel:`, etc.) est une main tendue vers l'OS. Liste
 *  blanche deliberee plutot que liste noire : le prochain schema d'evasion
 *  n'aura pas besoin d'etre connu a l'avance pour rester bloque. */
const ALLOWED_PROTOCOLS = new Set(['http:', 'https:'])

/** Domaine TikTok, et sous-domaines (www., m., us., ...). */
const TIKTOK_DOMAIN = 'tiktok.com'

/**
 * Fournisseurs de connexion tierce que le flux de connexion TikTok peut
 * legitimement emprunter (bouton "Continuer avec Google/Apple/Facebook").
 * Volontairement restreint aux hotes d'authentification connus plutot qu'au
 * domaine entier du fournisseur (ex. `accounts.google.com`, pas `google.com`)
 * pour ne pas rouvrir la porte a n'importe quelle page du fournisseur.
 */
const LOGIN_PROVIDER_DOMAINS = ['accounts.google.com', 'appleid.apple.com', 'facebook.com']

function parseUrl (url: string): URL | null {
  try {
    return new URL(url)
  } catch {
    // URL non parsable (schema absent, chaine malformee...) : jamais une
    // destination valide, donc jamais autorisee.
    return null
  }
}

/**
 * Un domaine correspond s'il est exactement `domain`, ou un sous-domaine de
 * `domain` (`x.domain`). Comparaison sur le hostname deja separe par l'URL
 * parser, jamais par sous-chaine sur l'URL brute : un test du type
 * `url.includes('tiktok.com')` laisserait passer
 * `https://evil-tiktok.com.attacker.net` (qui contient bien la sous-chaine
 * "tiktok.com" dans "evil-tiktok.com") ou `startsWith`/`endsWith` sur l'URL
 * complete laisserait passer `https://tiktok.com.attacker.net`. Le hostname
 * de `evil-tiktok.com.attacker.net` ne se termine ni par egalite ni par
 * `.tiktok.com` : il est rejete.
 */
function hostMatches (hostname: string, domain: string): boolean {
  return hostname === domain || hostname.endsWith(`.${domain}`)
}

/** Vrai si `url` utilise http: ou https:. Bloque tout schema qu'Electron
 *  remettrait a l'OS (deep links App Store, apps tierces...) ainsi que les
 *  URL non parsables. */
export function isAllowedProtocol (url: string): boolean {
  const parsed = parseUrl(url)
  return parsed !== null && ALLOWED_PROTOCOLS.has(parsed.protocol)
}

/** Vrai si `url` pointe vers tiktok.com ou un de ses sous-domaines. */
export function isTikTokHost (url: string): boolean {
  const parsed = parseUrl(url)
  return parsed !== null && hostMatches(parsed.hostname, TIKTOK_DOMAIN)
}

/** Vrai si `url` pointe vers un des fournisseurs de connexion tierce
 *  (Google, Apple, Facebook) que le flux de connexion TikTok peut emprunter. */
export function isLoginProviderHost (url: string): boolean {
  const parsed = parseUrl(url)
  if (parsed === null) return false
  return LOGIN_PROVIDER_DOMAINS.some(domain => hostMatches(parsed.hostname, domain))
}

/**
 * Destination autorisee pour une navigation `will-navigate` dans une vue de
 * compte : TikTok lui-meme, ou un detour legitime par un fournisseur de
 * connexion tierce (la connexion Google/Apple/Facebook de TikTok peut
 * rediriger la page entiere plutot que passer par une popup), en http/https
 * uniquement.
 */
export function isAllowedNavigationTarget (url: string): boolean {
  return isAllowedProtocol(url) && (isTikTokHost(url) || isLoginProviderHost(url))
}

/**
 * Destination autorisee pour une fenetre/popup demandee via
 * `window.open`/`target="_blank"` (setWindowOpenHandler). Restreinte aux
 * fournisseurs de connexion tierce : c'est le seul flux legitime connu qui
 * peut s'appuyer sur une popup plutot que sur une navigation en place.
 * TikTok lui-meme est exclu ici (contrairement a isAllowedNavigationTarget) :
 * aucun usage normal de ce grid de cellules n'a besoin qu'une page TikTok
 * ouvre une fenetre supplementaire.
 */
export function isAllowedPopupTarget (url: string): boolean {
  return isAllowedProtocol(url) && isLoginProviderHost(url)
}
