import datetime
from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, inspect, text
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Account(Base):
    __tablename__ = "accounts"

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(String, nullable=False, unique=True)
    device_profile = Column(String, nullable=False)
    comment_style = Column(String, nullable=False, default="casual")
    ramp_up_day = Column(Integer, nullable=False, default=1)
    # Jour du Protocole Peachtint (1..14). Distinct de ramp_up_day, qui portait
    # l'ancien palier d'actions autorisées.
    protocol_day = Column(Integer, nullable=False, default=1)
    role = Column(String, nullable=False, default="flagship")
    # Un compte protégé n'accepte aucune session : emma.ftpl est « ne pas toucher ».
    protected = Column(Boolean, nullable=False, default=False)
    status = Column(String, nullable=False, default="idle")
    created_at = Column(DateTime, nullable=False, default=datetime.datetime.now)

    sessions = relationship("WarmupSession", back_populates="account")


class WarmupSession(Base):
    __tablename__ = "sessions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False)
    started_at = Column(DateTime, nullable=False)
    ended_at = Column(DateTime, nullable=True)
    duration_seconds = Column(Integer, nullable=True)
    # Le mot-clé unique de la phase de recherche.
    keyword = Column(String, nullable=True)
    # Résultat de la phase 13-18' : vidéos de la niche sur 20 scrolls.
    fyp_niche_count = Column(Integer, nullable=True)
    fyp_verdict = Column(String, nullable=True)
    # Faux si la session a été coupée avant la fin des 18 minutes.
    completed = Column(Boolean, nullable=False, default=False)

    account = relationship("Account", back_populates="sessions")
    action_logs = relationship("ActionLog", back_populates="session")


class ActionLog(Base):
    __tablename__ = "action_logs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(Integer, ForeignKey("sessions.id"), nullable=False)
    action_type = Column(String, nullable=False)
    detail = Column(String, nullable=False, default="")
    timestamp = Column(DateTime, nullable=False, default=datetime.datetime.now)

    session = relationship("WarmupSession", back_populates="action_logs")


# Colonnes ajoutées après la première mise en base. SQLite ne les crée pas via
# `create_all` sur une table existante, donc on les ajoute à la main au
# démarrage. Chaque entrée est (table, colonne, type SQL, valeur par défaut).
_ADDED_COLUMNS = [
    ("accounts", "protocol_day", "INTEGER", "1"),
    ("accounts", "role", "VARCHAR", "'flagship'"),
    ("accounts", "protected", "BOOLEAN", "0"),
    ("sessions", "keyword", "VARCHAR", "NULL"),
    ("sessions", "fyp_niche_count", "INTEGER", "NULL"),
    ("sessions", "fyp_verdict", "VARCHAR", "NULL"),
    ("sessions", "completed", "BOOLEAN", "0"),
]


def migrate(engine) -> list[str]:
    """Ajoute les colonnes manquantes. Renvoie la liste de ce qui a été ajouté."""
    inspector = inspect(engine)
    applied: list[str] = []
    with engine.begin() as conn:
        for table, column, sql_type, default in _ADDED_COLUMNS:
            if table not in inspector.get_table_names():
                continue
            existing = {c["name"] for c in inspector.get_columns(table)}
            if column in existing:
                continue
            conn.execute(
                text(f"ALTER TABLE {table} ADD COLUMN {column} {sql_type} DEFAULT {default}")
            )
            applied.append(f"{table}.{column}")
    return applied
