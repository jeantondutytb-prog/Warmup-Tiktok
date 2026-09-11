import os

import pytest
import yaml

from app.core.coords import CoordMap, UncalibratedPoint, load_coords

RAW = {
    "screen": {"width": 375, "height": 812},
    "points": {
        "home_tab": {"x": 0.10, "y": 0.97, "calibrated": True},
        "search_icon": {"x": 0.92, "y": 0.076, "calibrated": False},
        "no_flag": {"x": 0.5, "y": 0.5},
    },
    "back_swipe": {"from": {"x": 0.01, "y": 0.5}, "to": {"x": 0.6, "y": 0.5}, "duration_ms": 250},
}


def test_percentages_convert_to_device_points():
    assert CoordMap(RAW).px("home_tab") == (37, 787)


def test_tapping_an_uncalibrated_point_is_refused():
    with pytest.raises(UncalibratedPoint) as excinfo:
        CoordMap(RAW).px("search_icon")
    assert "calibrate" in str(excinfo.value)


def test_a_point_without_a_flag_counts_as_uncalibrated():
    assert "no_flag" in CoordMap(RAW).uncalibrated()


def test_the_refusal_can_be_bypassed_for_calibration_itself():
    assert CoordMap(RAW).px("search_icon", require_calibrated=False) == (345, 61)


def test_unknown_point_raises_key_error():
    with pytest.raises(KeyError):
        CoordMap(RAW).px("nope")


def test_uncalibrated_list_is_sorted_and_excludes_verified_points():
    assert CoordMap(RAW).uncalibrated() == ["no_flag", "search_icon"]


def test_back_swipe_converts_to_points():
    assert CoordMap(RAW).back_swipe_px() == (3, 406, 225, 406, 250)


def test_the_shipped_config_parses_and_declares_the_iphone_xs():
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "coords.yaml")
    coords = load_coords(path)
    assert (coords.width, coords.height) == (375, 812)
    # Les repères des quatre phases ont été vérifiés par un tap réel le 03.09.
    from app.core.orchestrator import REQUIRED_POINTS
    uncalibrated = coords.uncalibrated()
    assert [p for p in REQUIRED_POINTS if p in uncalibrated] == []


def test_the_sidebar_sits_below_the_reaction_button():
    """Régression : les valeurs d'août tapaient le smiley au lieu du cœur.

    TikTok a ajouté un bouton de réaction en haut de la barre latérale, ce qui
    a poussé le cœur vers le bas. Un `btn_like` remonté au-dessus de 0.45
    retomberait sur le smiley.
    """
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "coords.yaml")
    coords = load_coords(path)
    assert coords.points["btn_like"].y_pct > 0.45
    assert coords.points["creator_avatar"].y_pct > 0.40


def test_shipped_config_has_no_duplicate_or_out_of_range_points():
    path = os.path.join(os.path.dirname(os.path.dirname(__file__)), "config", "coords.yaml")
    with open(path) as f:
        raw = yaml.safe_load(f)
    for name, point in raw["points"].items():
        assert 0.0 <= point["x"] <= 1.0, name
        assert 0.0 <= point["y"] <= 1.0, name
