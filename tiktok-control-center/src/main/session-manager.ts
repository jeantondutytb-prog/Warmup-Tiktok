import { app, session } from 'electron'
import type { Session } from 'electron'
import { stripElectronTokens } from '../core/user-agent'
import type { Account } from '../core/types'

/**
 * Prepare la session d'un compte : user-agent credible et proxy si configure.
 * Idempotent — appeler plusieurs fois pour le meme compte est sans effet de bord.
 */
export async function configureSession (account: Account): Promise<Session> {
  const ses = session.fromPartition(account.partition)

  // null = "decide for me" : on sert le user-agent desktop authentique par
  // defaut. C'est lui qui donne acces au defilement a la molette et aux
  // controles cliquables (fleches, like) de l'interface desktop de TikTok
  // dans une cellule portrait etroite — l'interface mobile n'offre ni l'un ni
  // l'autre (elle avance par swipe et n'affiche pas ces controles). Un
  // account.userAgent explicite passe toujours intact ; toMobileUserAgent
  // reste disponible pour qui veut forcer le mobile sur un compte precis.
  const ua = account.userAgent ?? stripElectronTokens(ses.getUserAgent(), app.getName())
  ses.setUserAgent(ua)

  if (account.proxy) {
    await ses.setProxy({ proxyRules: account.proxy.server })
  } else {
    await ses.setProxy({ mode: 'direct' })
  }

  return ses
}

/**
 * Repond aux demandes d'authentification proxy. A brancher une seule fois au
 * demarrage. Sans cela, un proxy authentifie fait echouer tous les chargements
 * en silence.
 *
 * `lookup` recoit la Session Electron a l'origine de la demande — pas une
 * chaine de partition ou de storagePath. Electron renvoie la meme instance de
 * Session pour une meme chaine de partition a chaque appel de
 * `session.fromPartition`, donc l'identite d'objet (`===`) est un test exact.
 * Faire correspondre l'id du compte au storagePath par sous-chaine serait
 * fragile : un id court et aleatoire peut apparaitre par coincidence dans un
 * chemin de fichier, et storagePath n'est meme pas garanti d'etre renseigne.
 */
export function installProxyAuthHandler (lookup: (ses: Session) => Account | undefined): void {
  app.on('login', (event, webContents, _details, authInfo, callback) => {
    if (!authInfo.isProxy) return
    if (!webContents) return
    const account = lookup(webContents.session)
    if (!account?.proxy?.username) return
    event.preventDefault()
    callback(account.proxy.username, account.proxy.password ?? '')
  })
}

/** Efface toutes les donnees d'un compte supprime. */
export async function destroySession (account: Account): Promise<void> {
  await session.fromPartition(account.partition).clearStorageData()
}
