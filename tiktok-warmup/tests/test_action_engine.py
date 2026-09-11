import asyncio
import os
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

from app.core.action_engine import ActionEngine
from app.core.coords import load_coords

COORDS = load_coords(
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "coords.yaml")
)


def make_engine(driver=None):
    mock_driver = driver or MagicMock()
    comments = {"casual": ["Super!", "Cool", "J'adore"]}
    # La carte réelle : un moteur sans coordonnées contournerait la
    # calibration, ce qui est exactement le défaut de la session #42.
    return ActionEngine(
        driver=mock_driver, comments=comments, comment_style="casual", coords=COORDS
    )


def test_scroll_feed():
    engine = make_engine()
    with patch("app.core.action_engine.asyncio.sleep", new_callable=AsyncMock):
        result = asyncio.get_event_loop().run_until_complete(engine.scroll_feed())
    assert "scroll" in result.lower()


def test_watch_video():
    engine = make_engine()
    with patch("app.core.action_engine.asyncio.sleep", new_callable=AsyncMock):
        result = asyncio.get_event_loop().run_until_complete(engine.watch_video())
    assert "watch" in result.lower()


def test_like_video_double_taps_the_centre_not_the_sidebar():
    """Régression session #43 : la barre latérale glisse selon le post — sur un
    carrousel à longue légende le cœur remonte de 419 à 390. Le like passe donc
    par le double-tap au centre, indépendant de cette géométrie."""
    engine = make_engine()
    with (
        patch("app.core.action_engine.asyncio.sleep", new_callable=AsyncMock),
        patch.object(ActionEngine, "_heart_is_red", new_callable=AsyncMock,
                     side_effect=[False, True]),
    ):
        result = asyncio.get_event_loop().run_until_complete(engine.like_video())

    assert result == "liked video"
    engine.driver.double_tap.assert_called_once_with(*COORDS.px("screen_center"))
    # Plus aucun tap sur une coordonnée de barre latérale.
    engine.driver.execute_script.assert_not_called()


def test_like_video_reports_a_missed_tap_instead_of_success():
    """Un tap qui n'allume pas le cœur ne doit jamais compter comme un like."""
    engine = make_engine()
    with (
        patch("app.core.action_engine.asyncio.sleep", new_callable=AsyncMock),
        patch.object(ActionEngine, "_heart_is_red", new_callable=AsyncMock,
                     side_effect=[False, False, False]),
    ):
        result = asyncio.get_event_loop().run_until_complete(engine.like_video())
    assert result.startswith("SKIP")
    assert "deux taps" in result


def test_like_video_retries_once_when_the_first_tap_is_lost():
    """Observé le 04.09 : un tap lancé pendant le chargement de la vidéo se
    perd, le suivant passe. Une reprise évite un abandon de phase injustifié."""
    engine = make_engine()
    with (
        patch("app.core.action_engine.asyncio.sleep", new_callable=AsyncMock),
        patch.object(ActionEngine, "_heart_is_red", new_callable=AsyncMock,
                     side_effect=[False, False, True]),
    ):
        result = asyncio.get_event_loop().run_until_complete(engine.like_video())
    assert result == "liked video (2e essai)"
    assert engine.driver.double_tap.call_count == 2


def test_like_video_reports_an_already_liked_video_distinctly():
    """Le double-tap ne peut pas retirer un like, mais il ne faut pas non plus
    compter une vidéo déjà likée comme un nouveau like."""
    engine = make_engine()
    with (
        patch("app.core.action_engine.asyncio.sleep", new_callable=AsyncMock),
        patch.object(ActionEngine, "_heart_is_red", new_callable=AsyncMock,
                     side_effect=[True, True]),
    ):
        result = asyncio.get_event_loop().run_until_complete(engine.like_video())
    assert result == "liked video (déjà liké)"


def test_like_video_confirms_a_real_like():
    engine = make_engine()
    with (
        patch("app.core.action_engine.asyncio.sleep", new_callable=AsyncMock),
        patch.object(ActionEngine, "_heart_is_red", new_callable=AsyncMock,
                     side_effect=[False, True]),
    ):
        result = asyncio.get_event_loop().run_until_complete(engine.like_video())
    assert result == "liked video"


def test_comment_on_video():
    engine = make_engine()
    with patch("app.core.action_engine.asyncio.sleep", new_callable=AsyncMock):
        result = asyncio.get_event_loop().run_until_complete(engine.comment_on_video())
    assert len(result) > 0


def test_execute_action_dispatches():
    engine = make_engine()
    with patch("app.core.action_engine.asyncio.sleep", new_callable=AsyncMock):
        result = asyncio.get_event_loop().run_until_complete(engine.execute_action("scroll"))
    assert "scroll" in result.lower()


def test_execute_action_unknown_raises():
    engine = make_engine()
    try:
        asyncio.get_event_loop().run_until_complete(engine.execute_action("unknown_action"))
        assert False, "Should have raised ValueError"
    except ValueError:
        pass


# ----------------------------------------- régression session #42 : onglets

def test_open_first_result_never_taps_a_tab():
    """L'ordre de la rangée d'onglets dépend de la requête : pour « filtre
    pellicule », « Boutique » occupait la position de « Vidéos » et la phase
    recherche s'est déroulée entière dans TikTok Shop."""
    engine = make_engine()
    with patch("app.core.action_engine.asyncio.sleep", new_callable=AsyncMock):
        result = asyncio.get_event_loop().run_until_complete(engine.open_first_result())

    assert result == "opened first result"
    tapped = [c.args[1] for c in engine.driver.execute_script.call_args_list]
    assert tapped == [dict(zip(("x", "y"), COORDS.px("result_first")))]
    forbidden = dict(zip(("x", "y"), COORDS.px("tab_videos", require_calibrated=False)))
    assert forbidden not in tapped


def test_tab_videos_is_no_longer_required_to_start():
    """Un repère intapable ne doit pas bloquer le démarrage."""
    from app.core.orchestrator import REQUIRED_POINTS
    assert "tab_videos" not in REQUIRED_POINTS
    assert "tab_videos" in COORDS.uncalibrated()


# --------------------------- régression session #46 : le fil qui se bloque

def test_scroll_reports_a_stuck_feed_instead_of_claiming_success():
    """Sur la session #46 le fil est resté bloqué huit captures d'affilée sur
    un post #republication, et `scroll_feed` renvoyait « scrolled feed »."""
    engine = make_engine()
    with (
        patch("app.core.action_engine.asyncio.sleep", new_callable=AsyncMock),
        patch.object(ActionEngine, "_take_screenshot_hash", new_callable=AsyncMock,
                     return_value=4242),
    ):
        result = asyncio.get_event_loop().run_until_complete(engine.scroll_feed())

    assert result.startswith("SKIP")
    assert engine.driver.execute_script.call_count == 3


def test_scroll_stays_clear_of_the_action_column_and_the_caption():
    engine = make_engine()
    with (
        patch("app.core.action_engine.asyncio.sleep", new_callable=AsyncMock),
        patch.object(ActionEngine, "_take_screenshot_hash", new_callable=AsyncMock,
                     side_effect=[1, 2]),
    ):
        asyncio.get_event_loop().run_until_complete(engine.scroll_feed())

    args = engine.driver.execute_script.call_args[0][1]
    assert args["fromX"] < 320, "le geste ne doit pas partir de la colonne d'actions"
    assert args["fromY"] < 680, "ni de la légende ou de la barre du bas"
    assert args["toY"] < args["fromY"]


def test_a_recovered_scroll_says_it_took_more_than_one_try():
    engine = make_engine()
    with (
        patch("app.core.action_engine.asyncio.sleep", new_callable=AsyncMock),
        patch.object(ActionEngine, "_take_screenshot_hash", new_callable=AsyncMock,
                     side_effect=[7, 7, 9]),
    ):
        result = asyncio.get_event_loop().run_until_complete(engine.scroll_feed())
    assert result == "scrolled feed (2e essai)"
