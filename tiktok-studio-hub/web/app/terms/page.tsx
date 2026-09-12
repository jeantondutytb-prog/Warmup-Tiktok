import Link from 'next/link'

export default function TermsPage () {
  return (
    <main style={{ maxWidth: 720, margin: '0 auto', padding: '48px 24px', color: '#eee', lineHeight: 1.6 }}>
      <p><Link href="/" style={{ color: '#25F4EE' }}>← Retour</Link></p>
      <h1 style={{ marginTop: 24 }}>Conditions d&apos;utilisation</h1>
      <p><strong>Dernière mise à jour :</strong> 12 septembre 2026</p>
      <p>
        En utilisant TikTok Studio Hub, vous acceptez ces conditions. L&apos;application est un outil
        personnel pour consulter les statistiques de vos comptes TikTok connectés.
      </p>
      <h2>Service</h2>
      <p>
        Le service dépend des API TikTok for Developers. TikTok peut modifier ou limiter l&apos;accès
        à tout moment.
      </p>
      <h2>Comptes TikTok</h2>
      <p>Vous devez être propriétaire ou autorisé à connecter chaque compte TikTok ajouté.</p>
      <h2>Responsabilité</h2>
      <p>L&apos;application est fournie « en l&apos;état », sans garantie. L&apos;éditeur n&apos;est pas responsable des pertes liées à l&apos;usage du service.</p>
      <h2>Contact</h2>
      <p>jeantondut@gmail.com</p>
    </main>
  )
}
