export interface SeedAccount {
  username: string
  role: string
  protected: boolean
}

/** Même liste que config/accounts.yaml — source d'affichage avant le premier sync Mac. */
export const SEED_ACCOUNTS: SeedAccount[] = [
  { username: 'emma.srpt', role: 'flagship', protected: false },
  { username: 'chloe.rtps', role: 'second', protected: false },
  { username: 'eva.drtp', role: 'lab', protected: false },
  { username: 'emma.ftpl', role: 'capiria', protected: true },
]
