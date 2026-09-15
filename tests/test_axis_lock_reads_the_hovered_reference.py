# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""With an arrow-key lock, the cursor on a REFERENCE — a corner, a midpoint,
any point of an edge — far from the locked line lands the snap on that
reference's foot, with the dotted guide (Rafael's review, B3, 04:20:
Tape from the wall's bottom edge, ↑, hover the window's corner → the guide
takes the window's height). The rule only read the cursor near the foot."""
from __future__ import annotations

import math

import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QVector3D
from PySide6.QtWidgets import QApplication

from core.edits import build_add_edges
from tools.tape import TapeMeasureTool


@pytest.fixture(scope="module")
def viewport():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    elif not isinstance(app, QApplication):
        pytest.skip("another Qt application flavour is already running")
    from views.viewport import Viewport
    vp = Viewport(None)
    vp.resize(1000, 700)
    vp.camera.set_aspect(1000, 700)
    vp.flash_status = lambda *a, **k: None
    return vp


def _wall_with_window(vp):
    sc = vp.scene
    sc.mesh.clear()
    vp.history.undo_stack.clear()
    wall = [QVector3D(0, 0, 0), QVector3D(6, 0, 0), QVector3D(6, 0, 3), QVector3D(0, 0, 3)]
    vp.history.execute(build_add_edges(sc, [(wall[i], wall[(i + 1) % 4]) for i in range(4)]))
    win = [QVector3D(3, 0, 1), QVector3D(4, 0, 1), QVector3D(4, 0, 2.2), QVector3D(3, 0, 2.2)]
    vp.history.execute(build_add_edges(sc, [(win[i], win[(i + 1) % 4]) for i in range(4)]))
    assert len(sc.mesh.faces) == 2
    return sc


def _tape_from_bottom_edge(vp, sc, x=1.0):
    tool = TapeMeasureTool()
    vp.set_active_tool(tool)
    tool.start_point = QVector3D(x, 0, 0)
    tool._edge = next(e for e in sc.mesh.edges
                      if abs(e.a.z()) < 1e-9 and abs(e.b.z()) < 1e-9)
    vp.axis_lock = "z"
    return tool


def _hover(vp, world):
    px = vp._world_to_pixel(world)
    assert px is not None
    vp._process_hover(QPointF(*px), Qt.NoModifier)
    return vp.last_snap


def _look(vp, yaw_deg, pitch_deg):
    vp.camera.target = QVector3D(3, 0, 1.5)
    vp.camera.distance = 10.0
    vp.camera.yaw = math.radians(yaw_deg)
    vp.camera.pitch = math.radians(pitch_deg)


def test_the_window_corner_gives_the_locked_line_its_height(viewport):
    sc = _wall_with_window(viewport)
    _look(viewport, -60.0, -20.0)                    # an oblique view, not a elevation
    _tape_from_bottom_edge(viewport, sc)
    snap = _hover(viewport, QVector3D(3, 0, 2.2))    # the window's top-left corner
    assert snap.kind == "from_point"
    assert (snap.point - QVector3D(1, 0, 2.2)).length() < 1e-6
    assert snap.guide is not None
    ref, foot = snap.guide
    assert (ref - QVector3D(3, 0, 2.2)).length() < 1e-6
    assert (foot - snap.point).length() < 1e-6
    viewport.axis_lock = None


def test_any_point_of_the_sill_is_a_reference_too(viewport):
    sc = _wall_with_window(viewport)
    _look(viewport, -60.0, -20.0)
    _tape_from_bottom_edge(viewport, sc)
    snap = _hover(viewport, QVector3D(3.6, 0, 1.0))  # on the sill, not a corner
    assert snap.kind in ("from_point", "midpoint")
    assert abs(snap.point.z() - 1.0) < 1e-6
    assert abs(snap.point.x() - 1.0) < 1e-6 and abs(snap.point.y()) < 1e-6
    viewport.axis_lock = None


def test_away_from_any_reference_the_lock_just_projects(viewport):
    sc = _wall_with_window(viewport)
    _look(viewport, -90.0, 0.0)
    _tape_from_bottom_edge(viewport, sc)
    snap = _hover(viewport, QVector3D(5.2, 0, 2.6))  # bare wall
    assert snap.kind == "axis"
    assert abs(snap.point.x() - 1.0) < 1e-6
    viewport.axis_lock = None


def test_the_tape_guide_lands_at_the_referenced_height(viewport):
    sc = _wall_with_window(viewport)
    _look(viewport, -60.0, -20.0)
    tool = _tape_from_bottom_edge(viewport, sc)
    _hover(viewport, QVector3D(3, 0, 2.2))
    ctx = viewport._build_ctx_at(viewport._world_to_pixel(QVector3D(3, 0, 2.2))) \
        if hasattr(viewport, "_build_ctx_at") else None
    from tools.base import ToolContext
    snap = viewport.last_snap
    tool.on_click(ToolContext(viewport=viewport, world=snap.point,
                              screen=QPointF(0, 0), modifiers=Qt.NoModifier, snap=snap))
    guides = viewport.scene.guides
    assert len(guides) == 1
    assert abs(guides[0].point.z() - 2.2) < 1e-6
    viewport.axis_lock = None
