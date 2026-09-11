"""Le Protocole Peachtint, en logique pure.

Ce module ne connaît ni Appium, ni WDA, ni la base : il ne fait que répondre
aux questions « quelle phase maintenant ? », « ai-je le droit de liker ? »,
« puis-je démarrer une session ? ». C'est ce qui le rend testable sans
iPhone branché.

Les chiffres viennent du document « Protocole Peachtint » (03.09.2026).
"""

import random
from dataclasses import dataclass
from datetime import datetime, timedelta

# --------------------------------------------------------------------------
# La session de 18 minutes
# --------------------------------------------------------------------------

SESSION_SECONDS = 18 * 60


@dataclass(frozen=True)
class Phase:
    name: str
    start_s: int
    end_s: int
    label: str

    def contains(self, elapsed_s: float) -> bool:
        return self.start_s <= elapsed_s < self.end_s

    @property
    def duration_s(self) -> int:
        return self.end_s - self.start_s


# L'ordre compte autant que le contenu : ouvrir l'app et foncer droit dans la
# recherche est en soi un motif non humain, d'où la phase FYP d'entrée.
PHASES: tuple[Phase, ...] = (
    Phase("fyp_entry", 0, 120, "Le FYP d'abord"),
    Phase("search", 120, 600, "Recherche — un seul mot-clé"),
    Phase("profiles", 600, 780, "Deux ou trois profils"),
    Phase("fyp_measure", 780, 1080, "Retour au FYP — c'est la mesure"),
)


def phase_at(elapsed_s: float) -> Phase | None:
    """La phase en cours après `elapsed_s` secondes, ou None si la session est finie."""
    for phase in PHASES:
        if phase.contains(elapsed_s):
            return phase
    return None


# --------------------------------------------------------------------------
# Plafonds sur 24 h glissantes
# --------------------------------------------------------------------------

# Colonne « ma reco warmup » du protocole — volontairement très en dessous des
# seuils tolérés par TikTok. On envoie un signal de catégorie, pas du volume.
DAILY_CAPS: dict[str, tuple[int, int]] = {
    "follow": (10, 15),
    "like": (20, 30),
    "comment": (0, 3),
    "post": (1, 1),
}

# Débit maximum d'abonnements par heure glissante.
FOLLOW_PER_HOUR = 5

# Plafonds internes à une session.
FOLLOWS_PER_SESSION = 3
PROFILES_PER_SESSION = 3


def daily_cap(action: str, rng: random.Random | None = None) -> int:
    """Tire le plafond du jour pour une action dans sa fourchette.

    La fourchette est tirée une fois par jour et par compte, pas à chaque
    appel : un plafond constant à 15 est lui-même un motif.
    """
    low, high = DAILY_CAPS[action]
    r = rng or random
    return r.randint(low, high)


def cap_remaining(action: str, used_24h: int, cap: int) -> int:
    """Combien d'actions restent avant d'atteindre le plafond du jour."""
    if action not in DAILY_CAPS:
        return 0
    return max(0, cap - used_24h)


def follow_rate_ok(follow_times: list[datetime], now: datetime | None = None) -> bool:
    """Vrai si un abonnement de plus respecte le débit de FOLLOW_PER_HOUR / h."""
    now = now or datetime.now()
    cutoff = now - timedelta(hours=1)
    recent = [t for t in follow_times if t > cutoff]
    return len(recent) < FOLLOW_PER_HOUR


# --------------------------------------------------------------------------
# Rotation des mots-clés
# --------------------------------------------------------------------------

def flatten_keywords(keywords: dict[str, list[str]]) -> list[str]:
    """Aplatit {fr: [...], en: [...]} en une liste stable, FR puis EN."""
    flat: list[str] = []
    for lang in ("fr", "en"):
        flat.extend(keywords.get(lang, []))
    for lang, words in keywords.items():
        if lang not in ("fr", "en"):
            flat.extend(words)
    return flat


def keyword_for_session(keywords: dict[str, list[str]], session_index: int) -> str:
    """Le mot-clé de la n-ième session d'un compte, en rotation cyclique.

    Un seul mot-clé par session : la liste entière dans une même session est
    exactement ce que le protocole interdit.
    """
    flat = flatten_keywords(keywords)
    if not flat:
        raise ValueError("aucun mot-clé configuré")
    return flat[session_index % len(flat)]


# --------------------------------------------------------------------------
# Cadence
# --------------------------------------------------------------------------

# Deux sessions par jour pendant sept jours, puis une seule en entretien.
RAMP_DAYS = 7
SESSIONS_PER_DAY_RAMP = 2
SESSIONS_PER_DAY_MAINTENANCE = 1

# Espacement minimum entre deux sessions d'un même compte.
MIN_GAP_SAME_ACCOUNT = timedelta(hours=4)

# Espacement minimum entre deux comptes sur le même appareil. Basculer entre
# trois comptes en vingt minutes est un des motifs listés par le protocole.
MIN_GAP_BETWEEN_ACCOUNTS = timedelta(minutes=30)


def sessions_allowed_today(protocol_day: int) -> int:
    return SESSIONS_PER_DAY_RAMP if protocol_day <= RAMP_DAYS else SESSIONS_PER_DAY_MAINTENANCE


@dataclass(frozen=True)
class CadenceCheck:
    ok: bool
    reason: str = ""
    retry_after: timedelta | None = None


def can_start_session(
    *,
    protocol_day: int,
    sessions_today: int,
    last_session_this_account: datetime | None,
    last_session_any_account: datetime | None,
    protected: bool = False,
    now: datetime | None = None,
) -> CadenceCheck:
    """Décide si une session peut démarrer maintenant.

    Refuse plutôt que d'attendre : c'est à l'appelant de replanifier, pour que
    le motif de refus reste visible dans les logs.
    """
    now = now or datetime.now()

    if protected:
        return CadenceCheck(False, "compte protégé — le protocole le classe « ne pas toucher »")

    allowed = sessions_allowed_today(protocol_day)
    if sessions_today >= allowed:
        return CadenceCheck(False, f"quota du jour atteint ({sessions_today}/{allowed})")

    if last_session_this_account is not None:
        gap = now - last_session_this_account
        if gap < MIN_GAP_SAME_ACCOUNT:
            return CadenceCheck(
                False,
                f"moins de {MIN_GAP_SAME_ACCOUNT} depuis la dernière session de ce compte",
                MIN_GAP_SAME_ACCOUNT - gap,
            )

    if last_session_any_account is not None:
        gap = now - last_session_any_account
        if gap < MIN_GAP_BETWEEN_ACCOUNTS:
            return CadenceCheck(
                False,
                f"moins de {MIN_GAP_BETWEEN_ACCOUNTS} depuis la session d'un autre compte",
                MIN_GAP_BETWEEN_ACCOUNTS - gap,
            )

    return CadenceCheck(True)


# --------------------------------------------------------------------------
# Signaux
# --------------------------------------------------------------------------

# Le protocole classe le replay au-dessus de la vue complète. Une vidéo courte
# qu'on laisse boucler une deuxième fois est le signal le plus fort qu'on
# puisse envoyer sans interaction.
REPLAY_MAX_VIDEO_SECONDS = 15

# En phase de recherche : liker environ une vidéo sur trois. Liker plus de 30 %
# de ce qu'on regarde figure dans les motifs qui font repérer, donc on reste
# juste en dessous.
SEARCH_LIKE_RATE = 0.30


def should_replay(video_seconds: int) -> bool:
    """Vrai si la vidéo est assez courte pour être laissée boucler une fois."""
    return video_seconds < REPLAY_MAX_VIDEO_SECONDS


def should_like_in_search(rng: random.Random | None = None) -> bool:
    r = rng or random
    return r.random() < SEARCH_LIKE_RATE


# --------------------------------------------------------------------------
# La mesure de fin de session
# --------------------------------------------------------------------------

FYP_MEASURE_SCROLLS = 20


def fyp_verdict(niche_videos: int) -> str:
    """Traduit le comptage de la phase 13–18′ en verdict.

    0–1 : le warmup n'a pas pris. 2 : en cours. 3+ : l'algorithme a compris.
    """
    if niche_videos <= 1:
        return "cold"
    if niche_videos == 2:
        return "warming"
    return "ready"


# --------------------------------------------------------------------------
# Budget d'une session
# --------------------------------------------------------------------------

@dataclass
class SessionBudget:
    """Suit ce qu'une session a le droit de faire, et ce qu'elle a déjà fait.

    Porte à la fois les plafonds 24 h (tirés au début du jour) et les règles
    internes à la session — dont « jamais deux abonnements d'affilée », qui
    n'est vérifiable qu'ici.
    """

    like_cap: int
    follow_cap: int
    comment_cap: int
    likes_24h: int = 0
    follows_24h: int = 0
    comments_24h: int = 0
    follows_this_session: int = 0
    profiles_this_session: int = 0
    last_profile_action_was_follow: bool = False
    follow_times: list[datetime] = None  # type: ignore[assignment]

    def __post_init__(self):
        if self.follow_times is None:
            self.follow_times = []

    def can_like(self) -> bool:
        return self.likes_24h < self.like_cap

    def can_comment(self) -> bool:
        return self.comments_24h < self.comment_cap

    def can_follow(self, now: datetime | None = None) -> tuple[bool, str]:
        if self.follows_this_session >= FOLLOWS_PER_SESSION:
            return False, f"déjà {FOLLOWS_PER_SESSION} abonnements sur cette session"
        if self.follows_24h >= self.follow_cap:
            return False, f"plafond 24 h atteint ({self.follows_24h}/{self.follow_cap})"
        if self.last_profile_action_was_follow:
            return False, "jamais deux abonnements d'affilée"
        if not follow_rate_ok(self.follow_times, now):
            return False, f"débit de {FOLLOW_PER_HOUR} abonnements/h atteint"
        return True, ""

    def record_like(self) -> None:
        self.likes_24h += 1

    def record_comment(self) -> None:
        self.comments_24h += 1

    def record_follow(self, now: datetime | None = None) -> None:
        self.follows_24h += 1
        self.follows_this_session += 1
        self.last_profile_action_was_follow = True
        self.follow_times.append(now or datetime.now())

    def record_profile_visit(self, followed: bool = False) -> None:
        self.profiles_this_session += 1
        if not followed:
            self.last_profile_action_was_follow = False

    def profiles_remaining(self) -> int:
        return max(0, PROFILES_PER_SESSION - self.profiles_this_session)
