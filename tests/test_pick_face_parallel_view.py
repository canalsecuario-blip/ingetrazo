# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""Face picking in the parallel camera (@pacaeiro, issue #37): «face
detection is identifying the face that is behind the one in front… it's
in CAMERA orthogonal (parallel) mode that the thing happens»."""
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


@pytest.fixture
def viewport():
    from views.viewport import Viewport
    vp = Viewport(None)
    vp.resize(1000, 700)
    vp.camera.set_aspect(1000, 700)
    return vp


def _front_and_back(vp):
    """A big face facing the camera and a SMALLER one 30 cm behind it —
    the coplanar tiebreak prefers the smaller face, so a tolerance that
    reaches 30 cm hands the back one over."""
    m = vp.scene.mesh
    front = m.add_face([V(0, 0, 0), V(4, 0, 0), V(4, 0, 3), V(0, 0, 3)])
    back = m.add_face([V(1, 0.3, 1), V(3, 0.3, 1), V(3, 0.3, 2), V(1, 0.3, 2)])
    vp.scene.version += 1
    vp.camera.target = V(2, 1, 1.5)
    vp.camera.distance = 8.0
    vp.camera.yaw = -math.pi / 2                 # a front view, along +y
    vp.camera.pitch = 0.0
    return front, back


@pytest.mark.parametrize("perspective", [True, False])
def test_the_face_in_front_wins_in_both_cameras(viewport, perspective):
    """The parallel camera's ray starts a far plane behind the eye, 10 km
    back; a tolerance taken from the ray parameter was a metre there, and
    the back face won. Measured from the eye it is a millimetre or so."""
    front, back = _front_and_back(viewport)
    viewport.camera.perspective = perspective
    px = viewport._world_to_pixel(V(2, 0, 1.5))
    face, group = viewport.pick_face_any(px[0], px[1])
    assert face is front and group is None
    assert viewport.pick_face(px[0], px[1]) is front


def test_truly_coplanar_faces_still_tie_break_by_size(viewport):
    """The tolerance is not gone: a small face drawn ON a big one (same
    depth) is still the one under the cursor, in the parallel camera too."""
    m = viewport.scene.mesh
    big = m.add_face([V(0, 0, 0), V(4, 0, 0), V(4, 0, 3), V(0, 0, 3)])
    small = m.add_face([V(1, 0, 1), V(3, 0, 1), V(3, 0, 2), V(1, 0, 2)])
    viewport.scene.version += 1
    viewport.camera.target = V(2, 1, 1.5)
    viewport.camera.distance = 8.0
    viewport.camera.yaw = -math.pi / 2
    viewport.camera.pitch = 0.0
    viewport.camera.perspective = False
    px = viewport._world_to_pixel(V(2, 0, 1.5))
    assert viewport.pick_face(px[0], px[1]) is small
    assert viewport.pick_face_any(px[0], px[1])[0] is small
