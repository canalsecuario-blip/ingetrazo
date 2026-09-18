# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""A shape comes out facing the way its plane does, whichever way you drag.

Marco, 2026-09-18: «a veces cuando dibujo un rectángulo parece que me sale
con la cara invertida… no sale blanco sino azul». Blue is the back side.

Read off his live scene through the bridge — three rectangles drawn on the
ground with the camera above (eye at z = +10), all three with normal
(0, 0, −1). Then measured across the four diagonals you can drag:

    right-down   normal -Z   blue
    left-up      normal -Z   blue
    right-up     normal +Z   white
    left-down    normal +Z   white

So it was never random: ``_corners`` walks «along u, then along v», and the
loop inherits the SIGN of that walk. Two of the four drags give a face
pointing backwards. The Rotated Rectangle did the same going anticlockwise;
Circle and Polygon are safe, because sweeping an angle never changes sign.

Not cosmetic. The back side travels into the .skp and into the BIM tagging,
so a wall can arrive inside-out somewhere else entirely.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QMouseEvent, QVector3D
from PySide6.QtWidgets import QApplication

from tools.base import face_the_plane, loop_normal

_app = QApplication.instance() or QApplication([])


def V(x, y, z=0.0):
    return QVector3D(float(x), float(y), float(z))


def _draw(tool_key, points):
    from views.main_window import MainWindow
    win = MainWindow()
    win.show()
    win.resize(1200, 800)
    _app.processEvents()
    vp = win.viewport
    win._activate_tool(tool_key)
    try:
        for w in points:
            px, py = vp._world_to_pixel(w)
            vp._last_mouse_pos = QPointF(px, py)
            vp._refresh_snap()
            vp._dispatch_tool_click(QMouseEvent(
                QMouseEvent.MouseButtonPress, QPointF(px, py),
                Qt.LeftButton, Qt.LeftButton, Qt.NoModifier))
        faces = vp.scene.mesh.faces
        return faces[0].normal() if faces else None
    finally:
        win._saved_version = vp.scene.version
        win.close()


@pytest.mark.parametrize("a,b", [
    (V(1, 3), V(4, 1)),      # right-down — was blue
    (V(4, 1), V(1, 3)),      # left-up    — was blue
    (V(1, 1), V(4, 3)),      # right-up
    (V(4, 3), V(1, 1)),      # left-down
])
def test_a_rectangle_on_the_ground_faces_up_from_every_diagonal(a, b):
    n = _draw("rectangle", [a, b])
    assert n is not None
    assert n.z() > 0.9, "the ground's front faces up, whoever is looking"


@pytest.mark.parametrize("third", [V(4, 3), V(4, -1)])
def test_the_rotated_rectangle_too_going_either_way_round(third):
    n = _draw("rotated_rect", [V(1, 1), V(4, 1), third])
    assert n is not None
    assert n.z() > 0.9


def test_the_circle_was_already_right():
    """Pinned rather than assumed: a swept angle cannot change sign, and
    that is why it never showed the bug."""
    n = _draw("circle", [V(2, 2), V(0, 0)])
    assert n is not None
    assert n.z() > 0.9


def test_a_loop_square_to_its_plane_is_left_alone():
    """A rotated rectangle stood upright on its base edge has no side
    facing the work plane; flipping it on a rounding error would be worse
    than leaving it."""
    de_pie = [V(0, 0, 0), V(2, 0, 0), V(2, 0, 1), V(0, 0, 1)]
    assert face_the_plane(de_pie, V(0, 0, 1)) == de_pie


def test_the_helper_reverses_only_what_points_away():
    plano = V(0, 0, 1)
    mirando = [V(0, 0), V(1, 0), V(1, 1), V(0, 1)]
    assert QVector3D.dotProduct(loop_normal(mirando), plano) > 0
    assert face_the_plane(mirando, plano) == mirando
    al_reves = list(reversed(mirando))
    assert face_the_plane(al_reves, plano) != al_reves
    assert QVector3D.dotProduct(
        loop_normal(face_the_plane(al_reves, plano)), plano) > 0
