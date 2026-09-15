# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""Pushing a rim piece right through a solid removes it (Marco, 2026-09-15:
an arc rounded the front face's corner, the corner sliver pushed to the
back face «debería eliminarme ese triángulo como lo hace SketchUp»).

The opening lands on the far face's rim, not inside it, so it is a notch
rather than a hole: the far face is trimmed to what remains — the arc
becomes its outline — and no cap is left behind. Short of the far face the
push is a blind recess, as before."""
from __future__ import annotations

import math

import pytest
from PySide6.QtGui import QVector3D as V
from PySide6.QtWidgets import QApplication

from core.orient import is_closed
from tools.arc import commit_arc


@pytest.fixture(scope="module")
def app():
    a = QApplication.instance()
    if a is None:
        a = QApplication([])
    elif not isinstance(a, QApplication):
        pytest.skip("another Qt application flavour is already running")
    return a


def _rounded_box(app):
    """A 2 m cube whose front face (y = 0) has its top-right corner rounded
    by an arc of radius 0.5; returns the viewport and the corner sliver."""
    from tests import test_pushpull_ux as T
    from views.viewport import Viewport
    vp = Viewport(None)
    vp.resize(1000, 700)
    vp.camera.set_aspect(1000, 700)
    vp.flash_status = lambda *a, **k: None
    T._cube(vp.scene, vp.history, size=2.0, height=2.0)
    c, r = V(1.5, 0, 1.5), 0.5
    pts = [c + V(r * math.cos(a), 0, r * math.sin(a))
           for a in [(math.pi / 2) * k / 8 for k in range(9)]]
    commit_arc(vp, pts)
    front = [f for f in vp.scene.mesh.faces if all(abs(v.y()) < 1e-9 for v in f.vertices)]
    assert len(front) == 2
    return vp, min(front, key=lambda f: f.area())


def _back(mesh):
    return [f for f in mesh.faces if all(abs(v.y() - 2.0) < 1e-6 for v in f.vertices)]


def test_pushing_the_corner_piece_through_trims_the_far_face(app):
    from tests import test_pushpull_ux as T
    vp, sliver = _rounded_box(app)
    m = vp.scene.mesh
    T._push(vp.scene, sliver, -2.0)
    assert is_closed(m)
    back = _back(m)
    assert len(back) == 1 and len(back[0].vertices) == 12     # the arc outline
    # No coplanar leftover at the back, no cap: 6 box faces + 8 strip quads.
    assert len(m.faces) == 6 + 8
    top = [f for f in m.faces if all(abs(v.z() - 2.0) < 1e-6 for v in f.vertices)]
    assert len(top) == 1 and max(v.x() for v in top[0].vertices) == pytest.approx(1.5)
    right = [f for f in m.faces if all(abs(v.x() - 2.0) < 1e-6 for v in f.vertices)]
    assert len(right) == 1 and max(v.z() for v in right[0].vertices) == pytest.approx(1.5)
    # The strip runs the whole depth.
    strip = [f for f in m.faces if len(f.vertices) == 4
             and any(abs(v.y()) < 1e-9 for v in f.vertices)
             and any(abs(v.y() - 2.0) < 1e-9 for v in f.vertices)
             and len({round(v.x(), 6) for v in f.vertices}) > 1
             and len({round(v.z(), 6) for v in f.vertices}) > 1]
    assert len(strip) == 8
    # One undo brings the sliver back.
    vp.history.undo()
    assert len(_back(m)[0].vertices) == 4


def test_pushing_past_the_far_face_stops_flush_and_trims_too(app):
    from tests import test_pushpull_ux as T
    from tools.pushpull import PushPullTool
    vp, sliver = _rounded_box(app)
    tool = PushPullTool()
    tool.base_face = sliver
    tool.dragging = True
    tool._anchor = sliver.centroid()
    tool._normal = sliver.normal()
    tool._attached, tool._prism_cap = tool._classify_base(vp.scene)
    tool._cap_positions = tool._cap_loop_positions(sliver)
    tool._compute_inward_limit(vp.scene)
    assert tool._limit_in == pytest.approx(2.0)
    tool.extrusion = -2.6                       # overshoot: clamps to the back
    tool._clamp_extrusion(None)
    assert tool.extrusion == pytest.approx(-2.0)
    tool._commit(T._StubViewport(vp.scene))
    m = vp.scene.mesh
    assert is_closed(m) and len(m.faces) == 14
    assert len(_back(m)[0].vertices) == 12


def test_short_of_the_far_face_is_still_a_recess(app):
    from tests import test_pushpull_ux as T
    vp, sliver = _rounded_box(app)
    m = vp.scene.mesh
    T._push(vp.scene, sliver, -1.94)
    assert is_closed(m)
    assert len(_back(m)[0].vertices) == 4                   # untouched
    floor = [f for f in m.faces if all(abs(v.y() - 1.94) < 1e-6 for v in f.vertices)]
    assert len(floor) == 1
