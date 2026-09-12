import Link from 'next/link'

export default function PrivacyPage () {
  return (
    <main style={{ maxWidth: 720, margin: '0 auto', padding: '48px 24px', color: '#eee', lineHeight: 1.6 }}>
      <p><Link href="/" style={{ color: '#25F4EE' }}>← Retour</Link></p>
      <h1 style={{ marginTop: 24 }}>Politique de confidentialité</h1>
      <p><strong>Dernière mise à jour :</strong> 12 septembre 2026</p>
      <p>
        TikTok Studio Hub (« l&apos;application ») permet de connecter vos comptes TikTok via OAuth
        et d&apos;afficher vos statistiques agrégées (abonnés, vues, likes, vidéos).
      </p>
      <h2>Données collectées</h2>
      <ul>
        <li>Identifiant TikTok (open_id), nom d&apos;affichage, avatar</li>
        <li>Statistiques de profil et de vidéos autorisées par les scopes OAuth</li>
        <li>Jetons d&apos;accès OAuth (stockés de façon sécurisée pour synchroniser vos stats)</li>
      </ul>
      <h2>Utilisation</h2>
      <p>Les données servent uniquement à afficher votre dashboard personnel. Nous ne vendons pas vos données.</p>
      <h2>Stockage</h2>
      <p>Les comptes connectés sont stockés sur l&apos;infrastructure Vercel (Blob Storage) associée au projet.</p>
      <h2>Contact</h2>
      <p>Pour toute question : jeantondut@gmail.com</p>
    </main>
  )
}
