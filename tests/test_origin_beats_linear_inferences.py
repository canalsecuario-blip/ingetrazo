# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""The world origin is a point inference and beats the linear ones (Marco,
2026-09-15: «me quiero poner en el origen y no se pone»). It sat behind
'from point' and the axis line, so a cursor aligned with an encouraged
point on the red axis clicked millimetres beside the origin — his scene
had eight stubs along X, none starting at (0, 0, 0)."""
from __future__ import annotations

import math

import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QVector3D
from PySide6.QtWidgets import QApplication

from core.edits import build_add_edges
from tools.base import ToolContext
from tools.line import LineTool


@pytest.fixture(scope="module")
def viewport():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    elif not isinstance(app, QApplication):
        pytest.skip("another Qt application flavour is already running")
    from views.viewport import Viewport
    vp = Viewport(None)
    vp.resize(1400, 900)
    vp.camera.set_aspect(1400, 900)
    vp.flash_status = lambda *a, **k: None
    return vp


def _plan_view(vp, distance):
    vp.camera.target = QVector3D(0.1, -0.05, 0.0)
    vp.camera.distance = distance
    vp.camera.yaw = math.radians(-90.0)
    vp.camera.pitch = math.radians(89.0)


def _hover(vp, world, off=(0, 0)):
    px = vp._world_to_pixel(world)
    vp._process_hover(QPointF(px[0] + off[0], px[1] + off[1]), Qt.NoModifier)
    return vp.last_snap


def test_the_origin_wins_over_a_from_point_on_the_axis(viewport):
    vp = viewport
    vp.scene.mesh.clear()
    vp.history.undo_stack.clear()
    # A stub on the red axis, as Marco's scene had; its end gets ENCOURAGED
    # (hovered), then the cursor comes to the origin — aligned with it.
    vp.history.execute(build_add_edges(
        vp.scene, [(QVector3D(0.8, 0, 0), QVector3D(1.0, 0, 0))]))
    _plan_view(vp, 0.7)                                   # zoomed right in
    tool = LineTool()
    vp.set_active_tool(tool)
    vp._encouraged = [QVector3D(0.8, 0, 0)]
    for off in ((0, 0), (3, 0), (-4, 1), (5, -3)):
        snap = _hover(vp, QVector3D(0, 0, 0), off)
        assert snap.kind == "origin", (off, snap.kind, snap.point)
        assert snap.point == QVector3D(0, 0, 0)


def test_the_origin_wins_over_the_axis_line_from_a_start_point(viewport):
    vp = viewport
    vp.scene.mesh.clear()
    vp.history.undo_stack.clear()
    _plan_view(vp, 0.7)
    tool = LineTool()
    vp.set_active_tool(tool)
    start = QVector3D(0.8, 0, 0)
    px = vp._world_to_pixel(start)
    vp._process_hover(QPointF(*px), Qt.NoModifier)
    tool.on_click(ToolContext(viewport=vp, world=start, screen=QPointF(*px),
                              modifiers=Qt.NoModifier, snap=vp.last_snap))
    for off in ((0, 0), (4, 0), (-5, 2)):
        snap = _hover(vp, QVector3D(0, 0, 0), off)
        assert snap.kind == "origin", (off, snap.kind, snap.point)
    # Away from it, the axis inference still runs the line along X.
    snap = _hover(vp, QVector3D(0.3, 0, 0), (0, 2))
    assert snap.kind in ("axis", "axis_inference")
    tool.on_cancel(vp)


def test_a_corner_on_the_origin_still_reads_as_the_origin(viewport):
    vp = viewport
    vp.scene.mesh.clear()
    vp.history.undo_stack.clear()
    vp.history.execute(build_add_edges(
        vp.scene, [(QVector3D(0, 0, 0), QVector3D(1.0, 0, 0))]))
    _plan_view(vp, 3.0)
    vp.set_active_tool(LineTool())
    snap = _hover(vp, QVector3D(0, 0, 0), (2, 1))
    assert snap.kind == "origin" and snap.point == QVector3D(0, 0, 0)
