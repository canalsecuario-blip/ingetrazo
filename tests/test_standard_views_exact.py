# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""Top and Bottom are exactly vertical (@pacaeiro, issue #45: «With Camera
in Parallel Projection Top and Bottom views are not straight (camera not
perpendicular to view)»). They sat at 89° to keep lookAt away from its
degenerate case; in the parallel camera that showed every vertical edge
as a short line."""
from __future__ import annotations

import math
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtGui import QVector3D
from PySide6.QtWidgets import QApplication

_app = QApplication.instance() or QApplication([])


def V(x, y, z=0.0):
    return QVector3D(float(x), float(y), float(z))


def _camera(view, perspective=False):
    from core.camera import OrbitCamera
    c = OrbitCamera()
    c.set_aspect(1000, 700)
    c.perspective = perspective
    c.set_view(view)
    return c


def _screen(c, p):
    q = (c.projection_matrix() * c.view_matrix()).map(p)
    return q.x(), q.y()


@pytest.mark.parametrize("view", ["top", "bottom"])
def test_a_vertical_edge_is_a_point_in_the_parallel_plan(view):
    c = _camera(view)
    a, b = _screen(c, V(0, 0, 0)), _screen(c, V(0, 0, 3))
    assert abs(a[0] - b[0]) < 1e-6 and abs(a[1] - b[1]) < 1e-6
    assert abs(abs(c.forward().z()) - 1.0) < 1e-9          # straight down / up


def test_the_screen_keeps_its_orientation_from_the_89_degree_days():
    """North up the screen in Top, x to the right; Bottom as it was."""
    top = _camera("top")
    o, n, e = _screen(top, V(0, 0, 0)), _screen(top, V(0, 3, 0)), _screen(top, V(3, 0, 0))
    assert n[1] > o[1] and e[0] > o[0]
    bottom = _camera("bottom")
    o, n, e = _screen(bottom, V(0, 0, 0)), _screen(bottom, V(0, 3, 0)), _screen(bottom, V(3, 0, 0))
    assert n[1] < o[1] and e[0] > o[0]


def test_the_camera_bases_do_not_degenerate():
    """camera_basis (hidden-line pass, sheets) and the view rotation read
    the same effective up: right and up stay unit vectors at the pole."""
    from core.hlr import camera_basis
    for view in ("top", "bottom"):
        c = _camera(view)
        _eye, right, up, fwd = camera_basis(c)
        assert abs(float((right ** 2).sum()) - 1.0) < 1e-9
        assert abs(float((up ** 2).sum()) - 1.0) < 1e-9
        assert abs(float((right * fwd).sum())) < 1e-9


def test_the_other_views_and_a_rolled_up_are_untouched():
    c = _camera("front")
    assert c.up_vector() == c.up
    c = _camera("iso")
    assert c.up_vector() == c.up
    top = _camera("top")
    top.up = V(1, 0, 0)                     # a plan turned on the sheet
    assert top.up_vector() == V(1, 0, 0)


def test_orbiting_out_of_the_top_view_still_works():
    c = _camera("top", perspective=True)
    c.orbit(0.0, 40.0, 700)                 # drag down: tip the model
    assert abs(c.pitch) < math.radians(90.0)
    _m, ok = c.view_matrix().inverted()
    assert ok
