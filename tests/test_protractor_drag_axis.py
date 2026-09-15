# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""Protractor click-drag tilts the instrument off the orthogonal planes.

Issue #10 (@pacaeiro): SketchUp's Protractor takes a click-AND-DRAG from the
vertex to set its axis along the drag, so the angle is measured (and the guide
placed) in a plane that is not one of the three axis planes. Rotate already
had the gesture; the Protractor now shares it. A plain click keeps the
inferred plane, as before.
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QVector3D

from core.history import History
from core.scene import Scene
from tools.base import ToolContext
from tools.protractor import ProtractorTool


class _Vp:
    def __init__(self, scene):
        self.scene = scene
        self.history = History(scene)

    def update(self):
        pass

    def flash_status(self, *a, **k):
        pass

    def _world_to_pixel(self, v):          # a plan: world (x, y) → 100 px/m
        return (v.x() * 100.0, v.y() * 100.0)


def _ctx(vp, x, y, z=0.0):
    return ToolContext(viewport=vp, world=QVector3D(x, y, z),
                       screen=QPointF(x * 100.0, y * 100.0),
                       modifiers=Qt.NoModifier, snap=None)


def test_a_drag_from_the_vertex_sets_the_axis_along_it():
    vp = _Vp(Scene())
    tool = ProtractorTool()
    tool.on_click(_ctx(vp, 1, 1))                 # press on the vertex…
    tool.on_hover(_ctx(vp, 1, 3))                 # …drag 2 m along +Y…
    tool.on_release(vp)                           # …and let go
    axis = tool._axis()
    assert (axis - QVector3D(0, 1, 0)).length() < 1e-6
    # The disc is no longer in plan: the guide lands in the plane normal
    # to the drag.
    tool.on_click(_ctx(vp, 3, 1))                 # base arm along +X
    tool.on_click(_ctx(vp, 1, 1, 2))              # 90° up (in the XZ plane)
    assert len(vp.scene.guides) == 1
    g = vp.scene.guides[0]
    assert abs(abs(g.direction.z()) - 1.0) < 1e-6
    assert (g.point - QVector3D(1, 1, 0)).length() < 1e-6


def test_a_plain_click_keeps_the_inferred_plane():
    vp = _Vp(Scene())
    tool = ProtractorTool()
    tool.on_click(_ctx(vp, 1, 1))
    tool.on_hover(_ctx(vp, 1.02, 1.01))           # 2 px of jitter, not a drag
    tool.on_release(vp)
    assert tool._custom_axis is None
    assert (tool._axis() - QVector3D(0, 0, 1)).length() < 1e-6


def test_the_tilt_is_forgotten_after_the_guide():
    vp = _Vp(Scene())
    tool = ProtractorTool()
    tool.on_click(_ctx(vp, 0, 0))
    tool.on_hover(_ctx(vp, 0, 2))
    tool.on_release(vp)
    tool.on_click(_ctx(vp, 2, 0))
    tool.on_click(_ctx(vp, 0, 0, 2))
    assert tool._custom_axis is None              # the next measurement starts flat
    assert not tool._axis_drag_armed
