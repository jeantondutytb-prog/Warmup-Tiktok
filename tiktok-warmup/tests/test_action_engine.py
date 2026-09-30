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


# ------------------------------------------------------- bascule de compte

KNOWN = ["alpha", "beta", "gamma"]


def _switch(screens):
    """Joue une bascule où chaque lecture d'écran renvoie l'écran suivant."""
    engine = make_engine()
    with (
        patch("app.core.action_engine.asyncio.sleep", new_callable=AsyncMock),
        patch.object(ActionEngine, "_tap_point", new_callable=AsyncMock),
        patch.object(ActionEngine, "_tap", new_callable=AsyncMock) as tap,
        patch.object(ActionEngine, "go_back", new_callable=AsyncMock),
        patch.object(ActionEngine, "_screen_text", new_callable=AsyncMock,
                     side_effect=screens),
    ):
        reason = asyncio.get_event_loop().run_until_complete(
            engine.switch_tiktok_account("beta", KNOWN))
    return reason, tap


def test_switch_is_a_no_op_when_the_target_is_already_open():
    reason, tap = _switch([[("@beta", 180, 200)]])
    assert reason == ""
    tap.assert_not_called()


def test_switch_taps_the_target_row_and_verifies_it():
    reason, tap = _switch([
        [("@alpha", 180, 200)],
        [("alpha", 150, 500), ("beta", 150, 570)],
        [("@beta", 180, 200)],
    ])
    assert reason == ""
    tap.assert_called_once_with(150, 570)


def test_switch_refuses_when_the_screen_shows_another_account():
    """Un tap de travers ne doit jamais laisser tourner une session sur le
    mauvais compte, surtout pas sur un compte protégé."""
    reason, _ = _switch([
        [("@alpha", 180, 200)],
        [("beta", 150, 570)],
        [("@gamma", 180, 200)],
    ])
    assert "gamma" in reason


def test_switch_reports_an_account_missing_from_the_picker():
    reason, tap = _switch([
        [("@alpha", 180, 200)],
        [("alpha", 150, 500)],
        [("alpha", 150, 500)],
    ])
    assert "absent" in reason
    tap.assert_not_called()


# ------------------------------------------------------------- commentaire

def _comment(screens):
    engine = make_engine()
    with (
        patch("app.core.action_engine.asyncio.sleep", new_callable=AsyncMock),
        patch.object(ActionEngine, "_tap", new_callable=AsyncMock) as tap,
        patch.object(ActionEngine, "_screen_text", new_callable=AsyncMock, side_effect=screens),
    ):
        result = asyncio.get_event_loop().run_until_complete(engine.comment_on_video())
    return result, tap, engine


def test_comment_types_into_the_bar_found_on_screen():
    result, tap, engine = _comment([
        [("Ajouter un commentaire...", 110, 764)],
        [("Ajouter un commentaire...", 110, 764)],
    ])
    assert result.startswith("commented: ")
    tap.assert_called_once_with(110, 764)
    typed = [c.args[0] for c in engine.driver.type_text.call_args_list]
    assert typed[-1] == "\n" and result.endswith(typed[0])


def test_comment_is_skipped_when_the_creator_closed_comments():
    result, tap, _ = _comment([[("Ce créateur a limité l'accès aux commentaires", 187, 764)]])
    assert result.startswith("SKIP")
    tap.assert_not_called()


def test_a_comment_still_in_the_field_is_not_reported_as_sent():
    result, _, _ = _comment([
        [("Ajouter un commentaire...", 110, 764)],
        [("Top", 60, 400)],
    ])
    assert result.startswith("SKIP")


def test_switch_taps_the_account_name_read_on_screen():
    """Régression 30.09 : le nom est passé en haut à gauche et le point fixe
    tapait le compteur « J'aime ». Le nom lu à l'écran fait foi, pas le @."""
    engine = make_engine()
    screens = [
        [("alpha ▾", 110, 120), ("@alpha", 70, 146), ("J'aime", 180, 201)],
        [("alpha", 150, 500), ("beta", 150, 570)],
        [("@beta", 180, 200)],
    ]
    with (
        patch("app.core.action_engine.asyncio.sleep", new_callable=AsyncMock),
        patch.object(ActionEngine, "_tap_point", new_callable=AsyncMock) as tap_point,
        patch.object(ActionEngine, "_tap", new_callable=AsyncMock) as tap,
        patch.object(ActionEngine, "_screen_text", new_callable=AsyncMock, side_effect=screens),
    ):
        reason = asyncio.get_event_loop().run_until_complete(
            engine.switch_tiktok_account("beta", KNOWN))
    assert reason == ""
    assert tap.call_args_list[0].args == (110, 120)
    assert all(c.args[0] != "display_name" for c in tap_point.call_args_list)


# ------------------------------------------------------- profil du créateur

def _screenshot_with(blobs):
    """Capture iPhone XS (3x) noire avec des taches rouges (x, y, w, h en pt)."""
    import base64, io
    from PIL import Image, ImageDraw
    img = Image.new("RGB", (1125, 2436), (0, 0, 0))
    d = ImageDraw.Draw(img)
    for x, y, w, h in blobs:
        d.ellipse([(x - w / 2) * 3, (y - h / 2) * 3, (x + w / 2) * 3, (y + h / 2) * 3],
                  fill=(254, 44, 85))
    buf = io.BytesIO()
    img.save(buf, "PNG")
    return base64.b64encode(buf.getvalue()).decode()


def _badge(blobs):
    engine = make_engine()
    engine.driver.get_screenshot_as_base64.return_value = _screenshot_with(blobs)
    return asyncio.get_event_loop().run_until_complete(engine._follow_badge())


def test_the_follow_badge_is_found_where_the_search_layout_puts_it():
    x, y = _badge([(345, 339, 22, 22)])
    assert abs(x - 345) <= 1 and abs(y - 339) <= 1


def test_a_liked_heart_is_not_mistaken_for_the_follow_badge():
    assert _badge([(345, 388, 29, 27)]) is None
    x, y = _badge([(345, 374, 22, 22), (345, 420, 29, 27)])
    assert abs(y - 374) <= 1


def _open_profile(badge, screen):
    engine = make_engine()
    with (
        patch("app.core.action_engine.asyncio.sleep", new_callable=AsyncMock),
        patch.object(ActionEngine, "_follow_badge", new_callable=AsyncMock, return_value=badge),
        patch.object(ActionEngine, "_tap", new_callable=AsyncMock) as tap,
        patch.object(ActionEngine, "_tap_point", new_callable=AsyncMock) as tap_point,
        patch.object(ActionEngine, "_screen_text", new_callable=AsyncMock, return_value=screen),
    ):
        result = asyncio.get_event_loop().run_until_complete(engine.open_creator_profile())
    return result, tap, tap_point


PROFILE = [("12", 60, 280), ("Suivis", 60, 300), ("Followers", 180, 300)]


def test_the_avatar_is_tapped_above_the_badge_never_on_it():
    """Régression 30.09 : sur une vidéo de recherche, `creator_avatar` tombait
    sur le + et abonnait le compte sans ouvrir de profil."""
    result, tap, _ = _open_profile((345, 339), PROFILE)
    assert result == "opened creator profile"
    x, y = tap.call_args.args
    assert x == 345 and y <= 339 - 20


def test_a_profile_that_did_not_open_is_reported_as_skip():
    result, _, _ = _open_profile((345, 339), [("Ajouter un commentaire...", 110, 764)])
    assert result.startswith("SKIP")


def test_without_badge_the_feed_avatar_point_is_used():
    result, tap, tap_point = _open_profile(None, PROFILE)
    tap_point.assert_awaited_once_with("creator_avatar")
    tap.assert_not_called()
