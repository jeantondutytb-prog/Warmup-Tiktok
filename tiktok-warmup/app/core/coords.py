"""Chargement de la carte de coordonnées.

Les points vivent dans `config/coords.yaml` en pourcentage d'écran, pour
qu'une calibration ne demande pas de toucher au Python et qu'un changement
d'appareil ne casse pas tout.
"""

from dataclasses import dataclass

import yaml


class UncalibratedPoint(RuntimeError):
    """Levée quand on tape un point marqué `calibrated: false`.

    Taper au hasard dans TikTok n'est pas neutre : un tap manqué peut liker,
    signaler ou quitter l'app. On refuse plutôt que de tenter.
    """


@dataclass(frozen=True)
class Point:
    name: str
    x_pct: float
    y_pct: float
    calibrated: bool

    def to_px(self, width: int, height: int) -> tuple[int, int]:
        return int(width * self.x_pct), int(height * self.y_pct)


@dataclass(frozen=True)
class Swipe:
    from_x_pct: float
    from_y_pct: float
    to_x_pct: float
    to_y_pct: float
    duration_ms: int


class CoordMap:
    def __init__(self, data: dict):
        screen = data["screen"]
        self.width: int = screen["width"]
        self.height: int = screen["height"]

        self.points: dict[str, Point] = {
            name: Point(name, p["x"], p["y"], bool(p.get("calibrated", False)))
            for name, p in data["points"].items()
        }

        back = data["back_swipe"]
        self.back_swipe = Swipe(
            back["from"]["x"], back["from"]["y"],
            back["to"]["x"], back["to"]["y"],
            back.get("duration_ms", 250),
        )

    def px(self, name: str, *, require_calibrated: bool = True) -> tuple[int, int]:
        """Coordonnées en points d'un repère nommé."""
        point = self.points.get(name)
        if point is None:
            raise KeyError(f"point inconnu dans coords.yaml : {name}")
        if require_calibrated and not point.calibrated:
            raise UncalibratedPoint(
                f"« {name} » n'est pas calibré. Lance `python -m scripts.calibrate {name}` "
                f"avec l'iPhone branché, puis reporte la valeur dans config/coords.yaml."
            )
        return point.to_px(self.width, self.height)

    def uncalibrated(self) -> list[str]:
        return sorted(n for n, p in self.points.items() if not p.calibrated)

    def back_swipe_px(self) -> tuple[int, int, int, int, int]:
        s = self.back_swipe
        return (
            int(self.width * s.from_x_pct), int(self.height * s.from_y_pct),
            int(self.width * s.to_x_pct), int(self.height * s.to_y_pct),
            s.duration_ms,
        )


def load_coords(path: str) -> CoordMap:
    with open(path) as f:
        return CoordMap(yaml.safe_load(f))
