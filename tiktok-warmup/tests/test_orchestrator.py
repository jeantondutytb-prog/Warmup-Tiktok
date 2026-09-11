import asyncio
import datetime
import pytest
from unittest.mock import patch, MagicMock, AsyncMock
from app.core.orchestrator import Orchestrator


def make_orchestrator(tmp_path=None):
    import tempfile, os, shutil, yaml
    config_dir = tmp_path or tempfile.mkdtemp()
    accounts_path = os.path.join(config_dir, "accounts.yaml")
    devices_path = os.path.join(config_dir, "devices.yaml")
    comments_path = os.path.join(config_dir, "comments.txt")
    keywords_path = os.path.join(config_dir, "keywords.yaml")
    coords_path = os.path.join(config_dir, "coords.yaml")

    with open(accounts_path, "w") as f:
        yaml.dump({"accounts": [
            {"username": "u1", "device_profile": "pixel_6", "comment_style": "casual"},
        ]}, f)
    with open(devices_path, "w") as f:
        yaml.dump({"devices": {"pixel_6": {"model": "Pixel 6", "resolution": "1080x2400", "android_version": "13", "dpi": 411}}}, f)
    with open(comments_path, "w") as f:
        f.write("# casual\nCool\nNice\n")
    with open(keywords_path, "w") as f:
        yaml.dump({"keywords": {"fr": ["filtre digicam"], "en": ["digicam filter"]}}, f)
    # La vraie carte de coordonnées, pour que les tests voient les mêmes points
    # non calibrés que la production.
    shutil.copy(
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "coords.yaml"),
        coords_path,
    )

    return Orchestrator(db_url="sqlite:///:memory:", config_dir=config_dir)


def test_orchestrator_init_creates_accounts():
    orch = make_orchestrator()
    status = orch.get_status()
    assert "u1" in status
    assert status["u1"]["status"] == "idle"


def test_get_status_returns_counters():
    orch = make_orchestrator()
    status = orch.get_status()
    assert "counters" in status["u1"]
    assert status["u1"]["counters"]["likes"] == 0


def test_subscribe_returns_queue():
    orch = make_orchestrator()
    queue = orch.subscribe()
    assert isinstance(queue, asyncio.Queue)


def test_start_stop_all():
    orch = make_orchestrator()
    with patch.object(orch, "_run_cycle", new_callable=AsyncMock):
        loop = asyncio.new_event_loop()
        loop.run_until_complete(orch.start_all())
        assert orch._cycle_task is not None
        loop.run_until_complete(orch.stop_all())
        assert orch.get_status()["u1"]["status"] == "idle"
        loop.close()


# ------------------------------------------------------------------ cadence

def _orch_with_accounts(accounts):
    import tempfile, os, shutil, yaml
    config_dir = tempfile.mkdtemp()
    with open(os.path.join(config_dir, "accounts.yaml"), "w") as f:
        yaml.dump({"accounts": accounts}, f)
    with open(os.path.join(config_dir, "devices.yaml"), "w") as f:
        yaml.dump({"devices": {"iphone_xs": {"model": "iPhone XS", "resolution": "375x812", "android_version": "-", "dpi": 458}}}, f)
    with open(os.path.join(config_dir, "comments.txt"), "w") as f:
        f.write("# casual\nCool\n")
    with open(os.path.join(config_dir, "keywords.yaml"), "w") as f:
        yaml.dump({"keywords": {"fr": ["filtre digicam", "filtre pellicule"], "en": ["digicam filter"]}}, f)
    shutil.copy(
        os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "config", "coords.yaml"),
        os.path.join(config_dir, "coords.yaml"),
    )
    # Base sur fichier : le gate de cadence ouvre plusieurs sessions SQLAlchemy,
    # et un :memory: distinct par connexion perdrait les écritures.
    db_path = os.path.join(tempfile.mkdtemp(), "t.db")
    return Orchestrator(db_url=f"sqlite:///{db_path}", config_dir=config_dir)


_WARM = {"username": "warm", "device_profile": "iphone_xs", "comment_style": "casual", "role": "flagship"}
_LOCKED = {"username": "locked", "device_profile": "iphone_xs", "comment_style": "casual", "role": "capiria", "protected": True}


def test_protected_account_is_refused_by_the_gate():
    orch = _orch_with_accounts([_WARM, _LOCKED])
    result = orch._cadence_gate("locked")
    assert not result.ok
    assert "protégé" in result.reason


def test_a_fresh_account_passes_the_gate():
    orch = _orch_with_accounts([_WARM])
    assert orch._cadence_gate("warm").ok


def test_unknown_account_is_refused():
    orch = _orch_with_accounts([_WARM])
    assert not orch._cadence_gate("ghost").ok


def test_gate_blocks_a_second_session_within_four_hours():
    from app.models.models import Account, WarmupSession
    orch = _orch_with_accounts([_WARM])
    with orch.Session() as db:
        account = db.query(Account).filter_by(username="warm").first()
        db.add(WarmupSession(
            account_id=account.id,
            started_at=datetime.datetime.now() - datetime.timedelta(hours=1),
        ))
        db.commit()
    result = orch._cadence_gate("warm")
    assert not result.ok
    assert result.retry_after is not None


def test_gate_blocks_another_account_within_thirty_minutes():
    from app.models.models import Account, WarmupSession
    other = {"username": "other", "device_profile": "iphone_xs", "comment_style": "casual"}
    orch = _orch_with_accounts([_WARM, other])
    with orch.Session() as db:
        account = db.query(Account).filter_by(username="other").first()
        db.add(WarmupSession(
            account_id=account.id,
            started_at=datetime.datetime.now() - datetime.timedelta(minutes=5),
        ))
        db.commit()
    result = orch._cadence_gate("warm")
    assert not result.ok
    assert "autre compte" in result.reason


def test_keyword_rotates_across_sessions():
    from app.models.models import Account, WarmupSession
    from app.core import protocol
    orch = _orch_with_accounts([_WARM])
    with orch.Session() as db:
        account_id = db.query(Account).filter_by(username="warm").first().id

    first = protocol.keyword_for_session(orch.keywords, orch._session_index(account_id))
    with orch.Session() as db:
        db.add(WarmupSession(account_id=account_id, started_at=datetime.datetime.now()))
        db.commit()
    second = protocol.keyword_for_session(orch.keywords, orch._session_index(account_id))
    assert first != second


def test_counts_24h_ignores_older_actions():
    from app.models.models import Account, WarmupSession, ActionLog
    orch = _orch_with_accounts([_WARM])
    now = datetime.datetime.now()
    with orch.Session() as db:
        account_id = db.query(Account).filter_by(username="warm").first().id
        ws = WarmupSession(account_id=account_id, started_at=now - datetime.timedelta(days=2))
        db.add(ws)
        db.commit()
        db.refresh(ws)
        db.add(ActionLog(session_id=ws.id, action_type="like", detail="récent",
                         timestamp=now - datetime.timedelta(hours=2)))
        db.add(ActionLog(session_id=ws.id, action_type="like", detail="vieux",
                         timestamp=now - datetime.timedelta(hours=30)))
        db.add(ActionLog(session_id=ws.id, action_type="follow", detail="récent",
                         timestamp=now - datetime.timedelta(minutes=10)))
        db.commit()

    counts, follow_times = orch._counts_24h(account_id)
    assert counts["like"] == 1
    assert counts["follow"] == 1
    assert len(follow_times) == 1


# -------------------------------------------------------------- mesure FYP

def _orch_with_finished_session():
    from app.models.models import Account, WarmupSession
    orch = _orch_with_accounts([_WARM])
    with orch.Session() as db:
        account_id = db.query(Account).filter_by(username="warm").first().id
        ws = WarmupSession(
            account_id=account_id,
            started_at=datetime.datetime.now() - datetime.timedelta(minutes=20),
            ended_at=datetime.datetime.now(),
            keyword="filtre digicam",
        )
        db.add(ws)
        db.commit()
        db.refresh(ws)
        return orch, ws.id


def test_a_finished_session_without_count_is_pending():
    orch, session_id = _orch_with_finished_session()
    pending = orch.pending_fyp()
    assert [p["session_id"] for p in pending] == [session_id]
    assert pending[0]["keyword"] == "filtre digicam"
    assert pending[0]["shots_dir"].endswith(str(session_id))


def test_recording_a_count_derives_the_verdict_and_clears_pending():
    orch, session_id = _orch_with_finished_session()
    result = orch.record_fyp_count(session_id, 3)
    assert result["verdict"] == "ready"
    assert orch.pending_fyp() == []


def test_a_low_count_reads_as_cold():
    orch, session_id = _orch_with_finished_session()
    assert orch.record_fyp_count(session_id, 1)["verdict"] == "cold"


def test_a_count_above_the_scroll_budget_is_refused():
    import pytest
    orch, session_id = _orch_with_finished_session()
    with pytest.raises(ValueError):
        orch.record_fyp_count(session_id, 21)
    with pytest.raises(ValueError):
        orch.record_fyp_count(session_id, -1)


def test_recording_on_an_unknown_session_raises():
    import pytest
    orch, _ = _orch_with_finished_session()
    with pytest.raises(KeyError):
        orch.record_fyp_count(9999, 2)


def test_advance_protocol_day_is_reflected_in_status():
    orch = _orch_with_accounts([_WARM])
    orch.advance_protocol_day("warm", 8)
    assert orch.get_status()["warm"]["protocol_day"] == 8


def test_protocol_day_eight_drops_to_one_session_per_day():
    from app.models.models import Account, WarmupSession
    from app.core import protocol
    orch = _orch_with_accounts([_WARM])
    orch.advance_protocol_day("warm", 8)
    assert protocol.sessions_allowed_today(8) == 1
    with orch.Session() as db:
        account_id = db.query(Account).filter_by(username="warm").first().id
        db.add(WarmupSession(
            account_id=account_id,
            started_at=datetime.datetime.now() - datetime.timedelta(hours=6),
        ))
        db.commit()
    result = orch._cadence_gate("warm")
    assert not result.ok
    assert "quota du jour" in result.reason


def test_pre_protocol_sessions_never_enter_the_fyp_queue():
    """Les sessions d'avant la bascule n'ont pas de mot-clé, donc pas de mesure."""
    from app.models.models import Account, WarmupSession
    orch, session_id = _orch_with_finished_session()
    with orch.Session() as db:
        account_id = db.query(Account).filter_by(username="warm").first().id
        db.add(WarmupSession(
            account_id=account_id,
            started_at=datetime.datetime.now() - datetime.timedelta(days=9),
            ended_at=datetime.datetime.now() - datetime.timedelta(days=9),
            keyword=None,
        ))
        db.commit()
    assert [p["session_id"] for p in orch.pending_fyp()] == [session_id]


# ------------------------------------------------- régressions de la session 42

@pytest.mark.asyncio
async def test_a_refused_action_is_never_written_to_the_log():
    """Régression : « SKIP — jamais deux abonnements d'affilée » comptait
    comme un abonnement, gonflant le plafond 24 h du lendemain."""
    from app.models.models import Account, WarmupSession, ActionLog
    orch, session_id = _orch_with_finished_session()
    with orch.Session() as db:
        username = db.query(Account).filter_by(username="warm").first().username

    await orch._record(session_id, username, "follow", "SKIP — jamais deux abonnements d'affilée")
    await orch._record(session_id, username, "follow", "SKIP")
    await orch._record(session_id, username, "follow", "followed from profile")

    with orch.Session() as db:
        rows = db.query(ActionLog).filter_by(session_id=session_id, action_type="follow").all()
    assert [r.detail for r in rows] == ["followed from profile"]


@pytest.mark.asyncio
async def test_a_refusal_still_reaches_the_dashboard():
    orch, session_id = _orch_with_finished_session()
    queue = orch.subscribe()
    await orch._record(session_id, "warm", "follow", "SKIP — plafond atteint")
    event = queue.get_nowait()
    assert event["type"] == "refused"
    assert "plafond atteint" in event["data"]


# --------------------------- régression session #42 : likes qui n'atterrissent pas

def _ticking(phase, step=1.0):
    """Une horloge de test qui avance : `_sleep_until` boucle sinon sans fin."""
    state = {"t": float(phase.start_s)}

    def elapsed():
        state["t"] += step
        return state["t"]

    return elapsed


def _search_phase_harness(like_results):
    """Monte une phase de recherche dont les likes renvoient `like_results`."""
    from unittest.mock import AsyncMock, MagicMock
    from app.core import protocol
    from app.models.models import Account

    orch = _orch_with_accounts([_WARM])
    with orch.Session() as db:
        account_id = db.query(Account).filter_by(username="warm").first().id
    from app.models.models import WarmupSession
    with orch.Session() as db:
        ws = WarmupSession(account_id=account_id, started_at=datetime.datetime.now(),
                           keyword="filtre pellicule")
        db.add(ws); db.commit(); db.refresh(ws)
        session_id = ws.id

    engine = MagicMock()
    engine.open_search = AsyncMock(return_value="searched: filtre pellicule")
    engine.open_first_result = AsyncMock(return_value="opened first result")
    engine.watch_fully = AsyncMock(return_value="watched 3s")
    engine.watch_briefly = AsyncMock(return_value="watched 3s (bref, sans replay)")
    engine.return_to_feed = AsyncMock(return_value="back on feed")
    engine.scroll_feed = AsyncMock(return_value="scrolled feed")
    engine.like_video = AsyncMock(side_effect=like_results)

    budget = protocol.SessionBudget(like_cap=25, follow_cap=12, comment_cap=2)
    return orch, engine, budget, session_id


@pytest.mark.asyncio
async def test_search_phase_aborts_after_two_missed_likes():
    """Neuf « likes » ont été journalisés alors que la phase tournait dans
    TikTok Shop. Deux ratés d'affilée doivent désormais arrêter la phase."""
    from app.models.models import ActionLog
    from app.core.protocol import PHASES

    miss = "SKIP — le cœur n'a pas changé après deux taps"
    orch, engine, budget, session_id = _search_phase_harness([miss] * 10)
    phase = next(p for p in PHASES if p.name == "search")

    with (
        patch("app.core.orchestrator.protocol.should_like_in_search", return_value=True),
        patch("app.core.orchestrator.asyncio.sleep", new_callable=AsyncMock),
    ):
        await orch._phase_search(
            username="warm", session_id=session_id, engine=engine, budget=budget,
            keyword="filtre pellicule", phase=phase, elapsed=_ticking(phase),
        )

    assert engine.like_video.await_count == 2
    with orch.Session() as db:
        likes = db.query(ActionLog).filter_by(session_id=session_id, action_type="like").count()
    assert likes == 0, "un like manqué ne doit jamais entrer dans le journal"
    assert budget.likes_24h == 0


@pytest.mark.asyncio
async def test_a_successful_like_resets_the_miss_counter():
    from app.core.protocol import PHASES
    miss = "SKIP — le cœur n'a pas changé après deux taps"
    orch, engine, budget, session_id = _search_phase_harness(
        [miss, "liked video", miss, "liked video", miss, miss]
    )
    phase = next(p for p in PHASES if p.name == "search")

    with (
        patch("app.core.orchestrator.protocol.should_like_in_search", return_value=True),
        patch("app.core.orchestrator.asyncio.sleep", new_callable=AsyncMock),
    ):
        await orch._phase_search(
            username="warm", session_id=session_id, engine=engine, budget=budget,
            keyword="k", phase=phase, elapsed=_ticking(phase),
        )

    # S'arrête sur les deux derniers ratés, pas avant.
    assert engine.like_video.await_count == 6
    assert budget.likes_24h == 2


# ------------------ montée en charge : un compte neuf ne like ni ne suit

@pytest.mark.asyncio
async def test_day_one_never_likes():
    """Le protocole n'autorise que scroll + watch aux jours 1-2. Sans cette
    porte, un compte neuf likerait dès la première session."""
    from app.core.protocol import PHASES
    from app.models.models import ActionLog

    orch, engine, budget, session_id = _search_phase_harness(["liked video"] * 10)
    phase = next(p for p in PHASES if p.name == "search")

    with (
        patch("app.core.orchestrator.protocol.should_like_in_search", return_value=True),
        patch("app.core.orchestrator.asyncio.sleep", new_callable=AsyncMock),
    ):
        await orch._phase_search(
            username="warm", session_id=session_id, engine=engine, budget=budget,
            keyword="k", phase=phase, elapsed=_ticking(phase),
            allowed={"scroll", "watch"},
        )

    engine.like_video.assert_not_awaited()
    with orch.Session() as db:
        assert db.query(ActionLog).filter_by(session_id=session_id, action_type="like").count() == 0


@pytest.mark.asyncio
async def test_day_one_skips_the_profiles_phase_entirely():
    from unittest.mock import AsyncMock as AM, MagicMock
    from app.core.protocol import PHASES
    orch, engine, budget, session_id = _search_phase_harness([])
    phase = next(p for p in PHASES if p.name == "profiles")
    engine.open_creator_profile = AM()
    engine.follow_from_profile = AM()
    engine.return_to_feed = AM()

    with patch("app.core.orchestrator.asyncio.sleep", new_callable=AsyncMock):
        await orch._phase_profiles(
            username="warm", session_id=session_id, engine=engine, budget=budget,
            phase=phase, elapsed=_ticking(phase), allowed={"scroll", "watch"},
        )

    engine.open_creator_profile.assert_not_awaited()
    engine.follow_from_profile.assert_not_awaited()
    assert budget.follows_24h == 0


@pytest.mark.asyncio
async def test_day_eleven_still_likes():
    from app.core.protocol import PHASES
    orch, engine, budget, session_id = _search_phase_harness(["liked video"] * 400)
    phase = next(p for p in PHASES if p.name == "search")

    with (
        patch("app.core.orchestrator.protocol.should_like_in_search", return_value=True),
        patch("app.core.orchestrator.asyncio.sleep", new_callable=AsyncMock),
    ):
        await orch._phase_search(
            username="warm", session_id=session_id, engine=engine, budget=budget,
            keyword="k", phase=phase, elapsed=_ticking(phase),
            allowed={"scroll", "watch", "like", "follow", "visit_profile", "comment"},
        )
    assert engine.like_video.await_count >= 1


@pytest.mark.asyncio
async def test_force_never_overrides_a_protected_account():
    """La cadence se contourne ; « ne pas toucher » ne se contourne pas."""
    orch = _orch_with_accounts([_WARM, _LOCKED])
    queue = orch.subscribe()
    await orch.start_account("locked", force=True)
    await asyncio.sleep(0.3)
    events = []
    while not queue.empty():
        events.append(queue.get_nowait())
    refused = [e for e in events if e["type"] == "refused"]
    assert refused and "protégé" in refused[0]["data"]


@pytest.mark.asyncio
async def test_the_session_always_starts_from_the_feed():
    """Régression session #44 : la session a démarré sur la page profil et y a
    scrollé la grille deux minutes, puis ouvert le menu hamburger — sur un
    profil, la loupe du fil est le ☰."""
    from unittest.mock import AsyncMock as AM, MagicMock
    from app.core.protocol import PHASES
    orch, engine, budget, session_id = _search_phase_harness([])
    phase = next(p for p in PHASES if p.name == "fyp_entry")
    engine.return_to_feed = AM(return_value="back on feed")

    with patch("app.core.orchestrator.asyncio.sleep", new_callable=AsyncMock):
        await orch._phase_fyp_entry(
            username="warm", session_id=session_id, engine=engine, budget=budget,
            phase=phase, elapsed=_ticking(phase), allowed={"scroll", "watch"},
        )

    engine.return_to_feed.assert_awaited()
    # Le retour au fil précède toute lecture de vidéo.
    assert engine.return_to_feed.await_count >= 1


@pytest.mark.asyncio
async def test_the_entry_phase_never_replays_off_niche_videos():
    """Le fil d'un compte peut être mal calibré. Vue complète et replay sont
    les deux signaux les plus forts du protocole : les envoyer hors niche
    entraîne l'algorithme dans la mauvaise direction."""
    from unittest.mock import AsyncMock as AM
    from app.core.protocol import PHASES
    orch, engine, budget, session_id = _search_phase_harness([])
    phase = next(p for p in PHASES if p.name == "fyp_entry")
    engine.return_to_feed = AM(return_value="back on feed")
    engine.watch_briefly = AM(return_value="watched 3s (bref, sans replay)")
    engine.watch_fully = AM(return_value="watched 12s + replay")

    with patch("app.core.orchestrator.asyncio.sleep", new_callable=AsyncMock):
        await orch._phase_fyp_entry(
            username="warm", session_id=session_id, engine=engine, budget=budget,
            phase=phase, elapsed=_ticking(phase), allowed={"scroll", "watch"},
        )

    engine.watch_fully.assert_not_awaited()
    assert engine.watch_briefly.await_count >= 1
