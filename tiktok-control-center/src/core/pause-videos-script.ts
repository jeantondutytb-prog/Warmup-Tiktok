/**
 * Seul script que ce projet injecte dans une vue de compte (via
 * `webContents.executeJavaScript` dans `ViewManager`). Il met en pause la
 * lecture video locale des cellules non focalisees, pour eviter que plusieurs
 * lecteurs simultanes ne saturent le processeur.
 *
 * C'est un controle de lecture media local : aucune interaction n'est envoyee
 * au compte TikTok. En particulier, ce script ne doit jamais simuler une
 * entree utilisateur (clic, frappe, defilement) — c'est une regle dure du
 * projet, verifiee automatiquement par `tests/view-script.test.ts`.
 */
export const PAUSE_VIDEOS_SCRIPT =
  'document.querySelectorAll("video").forEach(v => v.pause()); undefined'
