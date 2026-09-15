# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""The hovered edge stays acquired after the cursor leaves it.

SketchUp's parallel inference (Rafael's review, 2026-09-10): while drawing a
line you brush an off-axis wall with the cursor, move away, and the draw locks
parallel to that wall (magenta «Paralelo a arista»). Drawing parallel means
drawing AWAY from the edge, so the reference must survive the cursor leaving
it. PR #21 briefly re-assigned the reference on every move (``_acquired_edge =
_hover_edge``), which dropped it the moment the cursor left the edge and
silently killed the inference; no test noticed. This one does.
"""
from __future__ import annotations

import os

import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QVector3D


def V(x, y, z=0.0):
    return QVector3D(float(x), float(y), float(z))


def _viewport():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    elif not isinstance(app, QApplication):
        pytest.skip("another Qt application flavour is already running")
    from views.viewport import Viewport
    vp = Viewport(None)
    vp.resize(1000, 600)
    vp.camera.set_aspect(1000, 600)
    vp.flash_status = lambda *a, **k: None
    vp.camera.set_view("top")
    vp.camera.target = V(3, 2, 0)
    vp.camera.distance = 12
    return vp


def test_the_hovered_edge_survives_the_cursor_leaving_it():
    from tools.base import ToolContext
    from tools.line import LineTool
    vp = _viewport()
    # An off-axis wall (27°): the axis inference never claims it, so the
    # parallel lock is the only way to draw along it.
    vp.scene.mesh.add_edge(V(0, 0, 0), V(4, 2, 0))
    vp.scene.version += 1
    tool = LineTool()
    vp.set_active_tool(tool)
    tool.on_click(ToolContext(viewport=vp, world=V(1, 4, 0), screen=QPointF(0, 0),
                              modifiers=Qt.NoModifier, snap=None))
    assert tool.start_point is not None                # a segment is under way

    on_edge_px = vp._world_to_pixel(V(2, 1, 0))         # the wall's body
    vp._process_hover(QPointF(*on_edge_px), Qt.NoModifier)
    assert vp._hover_edge is not None
    assert vp._acquired_edge is vp._hover_edge

    away_px = vp._world_to_pixel(V(4, 5.5, 0))          # empty space, off the wall
    vp._process_hover(QPointF(*away_px), Qt.NoModifier)
    assert vp._hover_edge is None                       # nothing under the cursor…
    assert vp._acquired_edge is not None                # …but the wall is remembered
    assert (vp._acquired_edge.a - V(0, 0, 0)).length() < 1e-6
    assert (vp._acquired_edge.b - V(4, 2, 0)).length() < 1e-6


def test_the_reference_is_dropped_once_nothing_is_being_drawn():
    from tools.base import ToolContext
    from tools.line import LineTool
    vp = _viewport()
    vp.scene.mesh.add_edge(V(0, 0, 0), V(4, 2, 0))
    vp.scene.version += 1
    tool = LineTool()
    vp.set_active_tool(tool)
    tool.on_click(ToolContext(viewport=vp, world=V(1, 4, 0), screen=QPointF(0, 0),
                              modifiers=Qt.NoModifier, snap=None))
    vp._process_hover(QPointF(*vp._world_to_pixel(V(2, 1, 0))), Qt.NoModifier)
    assert vp._acquired_edge is not None
    tool.start_point = None                             # Esc / segment finished
    vp._process_hover(QPointF(*vp._world_to_pixel(V(4, 5.5, 0))), Qt.NoModifier)
    assert vp._acquired_edge is None                    # never stale across draws
