"""Zoom Extents frames the model as the camera looks at it NOW.

It used to frame the box's bounding sphere, which does not depend on the
view: after an orbit or a standard view a second Zoom Extents gave back the
same target and distance and seemed to do nothing, with a tower at 9 % of
the screen seen from above (Marco: «a veces no hace efecto, en determinadas
posiciones»), and a tall window cut the model at the sides."""
from __future__ import annotations

import math

import pytest
from PySide6.QtGui import QVector3D as V, QVector4D

from core.camera import MAX_DISTANCE, OrbitCamera


def _screen(cam, lo, hi):
    """(half-span of the box on screen, every corner inside the window)."""
    mvp = cam.projection_matrix() * cam.view_matrix()
    xs, ys = [], []
    for x in (lo.x(), hi.x()):
        for y in (lo.y(), hi.y()):
            for z in (lo.z(), hi.z()):
                p = mvp.map(QVector4D(x, y, z, 1.0))
                xs.append(p.x() / p.w())
                ys.append(p.y() / p.w())
    span = max(max(xs) - min(xs), max(ys) - min(ys)) / 2.0
    inside = all(abs(v) <= 1.0 + 1e-4 for v in xs + ys)
    return span, inside


BOXES = {
    "tower": (V(0, 0, 0), V(5, 5, 40)),
    "wall": (V(0, 0, 0), V(20, 0.2, 3)),
    "plaza": (V(0, 0, 0), V(30, 20, 0.2)),
    "street": (V(0, 0, 0), V(1000, 5, 0)),
}


@pytest.mark.parametrize("box", sorted(BOXES))
@pytest.mark.parametrize("view", ["top", "right", "front", "iso"])
@pytest.mark.parametrize("perspective", [True, False])
@pytest.mark.parametrize("aspect", [1.8, 0.6])
def test_the_model_fills_the_window_in_any_view(box, view, perspective, aspect):
    lo, hi = BOXES[box]
    cam = OrbitCamera()
    cam.aspect, cam.perspective = aspect, perspective
    cam.set_view(view)
    cam.fit_box(lo, hi)
    span, inside = _screen(cam, lo, hi)
    assert inside
    assert span == pytest.approx(1 / 1.1, abs=0.02)


def test_a_second_zoom_extents_after_an_orbit_is_not_a_no_op():
    lo, hi = BOXES["plaza"]
    cam = OrbitCamera()
    cam.aspect = 1.8
    cam.fit_box(lo, hi)
    before = (V(cam.target), cam.distance)
    cam.yaw, cam.pitch = math.radians(-95), math.radians(-30)
    cam.fit_box(lo, hi)
    assert (cam.target, cam.distance) != before
    assert _screen(cam, lo, hi)[1]


def test_a_point_and_a_huge_model_stay_in_range():
    cam = OrbitCamera()
    cam.fit_box(V(1, 1, 1), V(1, 1, 1))
    assert cam.distance > 0 and math.isfinite(cam.distance)
    cam.fit_box(V(0, 0, 0), V(60000, 60000, 10))
    assert cam.distance <= MAX_DISTANCE
