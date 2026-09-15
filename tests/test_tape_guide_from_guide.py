# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""Tape Measure pulls a guide from a GUIDE, not only from an edge.

Issue #22 (@pacaeiro): in SketchUp you click a guide line's body with the
Tape and drag (or type) to lay a second guide parallel to it — that is how a
grid of guides is built. Ours only accepted mesh edges as the source, because
the tool picked with the mesh edge picker, which never sees guides.
"""
from __future__ import annotations

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QVector3D

from core.guide import Guide
from core.history import History
from core.scene import Scene
from core.snap import SnapResult
from tools.base import ToolContext
from tools.tape import TapeMeasureTool


def V(x, y, z=0.0):
    return QVector3D(float(x), float(y), float(z))


class _Vp:
    """A viewport stub that picks the way the real one does for this case:
    no mesh edge under the cursor, the guide within threshold."""

    def __init__(self, scene, guide=None):
        self.scene = scene
        self.history = History(scene)
        self._guide = guide

    def update(self):
        pass

    def flash_status(self, *a, **k):
        pass

    def pick_edge(self, x, y):
        return None

    def pick_guide(self, x, y):
        return self._guide


def _ctx(vp, x, y, kind="on_edge"):
    snap = SnapResult(V(x, y), kind, (0, 0, 0)) if kind else None
    return ToolContext(viewport=vp, world=V(x, y), screen=QPointF(x * 100, y * 100),
                       modifiers=Qt.NoModifier, snap=snap)


def test_a_guide_pulled_from_a_guide_is_parallel_at_the_offset():
    scene = Scene()
    first = Guide(V(0, 1, 0), V(1, 0, 0))            # along X at y = 1
    scene.guides.append(first)
    vp = _Vp(scene, guide=first)
    tool = TapeMeasureTool()
    tool.on_click(_ctx(vp, 3, 1))                    # on the guide's body
    assert tool._edge is first
    tool.on_click(_ctx(vp, 3, 3.5, kind=None))       # 2.5 m away
    assert len(scene.guides) == 2
    g = scene.guides[1]
    assert abs(abs(QVector3D.dotProduct(g.direction, V(1, 0, 0))) - 1.0) < 1e-6
    assert abs(g.point.y() - 3.5) < 1e-6


def test_a_typed_distance_places_the_guide_exactly():
    scene = Scene()
    first = Guide(V(0, 1, 0), V(1, 0, 0))
    scene.guides.append(first)
    vp = _Vp(scene, guide=first)
    tool = TapeMeasureTool()
    tool.on_click(_ctx(vp, 3, 1))
    tool.on_hover(_ctx(vp, 3, 2.2, kind=None))       # pulling towards +Y
    assert tool.on_value(vp, 2.0)
    assert len(scene.guides) == 2
    assert abs(scene.guides[1].point.y() - 3.0) < 1e-6
    vp.history.undo()
    assert len(scene.guides) == 1


def test_a_guide_point_is_not_a_source():
    scene = Scene()
    pt = Guide(V(2, 2, 0))                           # a guide POINT
    scene.guides.append(pt)
    vp = _Vp(scene, guide=pt)
    tool = TapeMeasureTool()
    tool.on_click(_ctx(vp, 2, 2))
    assert tool._edge is None                        # measure mode instead


def test_the_crossing_of_two_guides_measures_instead_of_pulling():
    scene = Scene()
    first = Guide(V(0, 1, 0), V(1, 0, 0))
    scene.guides.append(first)
    vp = _Vp(scene, guide=first)
    tool = TapeMeasureTool()
    tool.on_click(_ctx(vp, 2, 1, kind="intersection"))   # the green X is a point
    assert tool._edge is None
