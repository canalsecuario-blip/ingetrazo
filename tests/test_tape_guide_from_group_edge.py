# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""The Tape pulls a guide off an edge INSIDE a group or component (#28).

@pacaeiro: «Tape cannot create Guidelines from edges that are inside of a
Group or Component.»

The tool asked ``pick_edge``, which only ever sees the loose mesh, so a
click on a component's edge found nothing and fell through to plain
measuring. SketchUp reads a group's edges from the outside without opening
it, and so does the rest of IngeTrazo: ``pick_edge_any`` — built for the
Down-arrow reference lock (issue #10) — returns a group's edge as a world
pseudo-edge. The Tape now asks that one.

Guides pulled from guides (issue #22) keep working: the guide fallback runs
only when no edge at all was found, and a guide is not an edge.
"""
from __future__ import annotations

from types import SimpleNamespace

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QVector3D

from core.history import History
from core.scene import Scene
from tools.base import ToolContext
from tools.tape import TapeMeasureTool


def V(x, y, z=0.0):
    return QVector3D(float(x), float(y), float(z))


class _Vp:
    """A stub that answers the two pickers differently, which is the whole
    point: ``pick_edge`` is the loose mesh, ``pick_edge_any`` also reaches
    inside groups."""

    def __init__(self, scene, loose=None, grouped=None):
        self.scene = scene
        self.history = History(scene)
        self._loose = loose
        self._grouped = grouped
        self.flashed = []

    def update(self):
        pass

    def flash_status(self, text, *a, **k):
        self.flashed.append(text)

    def pick_edge(self, x, y):
        return self._loose

    def pick_edge_any(self, x, y):
        return self._grouped if self._grouped is not None else self._loose

    def pick_guide(self, x, y):
        return None

    def pick_face(self, x, y):
        return None

    def pick_group(self, x, y):
        return None


def _ctx(vp, x, y, z=0.0, snap=None):
    return ToolContext(viewport=vp, world=V(x, y, z), screen=QPointF(0, 0),
                       modifiers=Qt.NoModifier, snap=snap)


def _pseudo_edge(a, b):
    """What pick_edge_any hands back for a group's edge: a world-space
    stand-in carrying the same ``.a`` / ``.b``."""
    return SimpleNamespace(a=a, b=b, in_group=True)


def test_a_group_edge_starts_guide_mode():
    scene = Scene()
    edge = _pseudo_edge(V(0, 0), V(4, 0))
    vp = _Vp(scene, loose=None, grouped=edge)
    tool = TapeMeasureTool()
    tool.on_click(_ctx(vp, 1, 0))
    assert tool._edge is edge, "the group's edge must be the guide source"


def test_and_the_second_click_places_the_guide():
    scene = Scene()
    vp = _Vp(scene, loose=None, grouped=_pseudo_edge(V(0, 0), V(4, 0)))
    tool = TapeMeasureTool()
    tool.on_click(_ctx(vp, 1, 0))          # grab the group's edge
    tool.on_click(_ctx(vp, 1, 2))          # pull 2 m off it
    assert len(scene.guides) == 1
    g = scene.guides[0]
    assert g.is_line
    assert abs(g.point.y() - 2.0) < 1e-6


def test_a_loose_edge_still_works():
    """The path that already worked, pinned."""
    scene = Scene()
    edge = _pseudo_edge(V(0, 0), V(4, 0))
    vp = _Vp(scene, loose=edge, grouped=edge)
    tool = TapeMeasureTool()
    tool.on_click(_ctx(vp, 1, 0))
    assert tool._edge is edge


def test_an_endpoint_snap_still_measures_instead_of_guiding():
    """Clicking the END of an edge measures; only its BODY pulls a guide.
    Unchanged by reaching into groups."""
    scene = Scene()
    vp = _Vp(scene, loose=None, grouped=_pseudo_edge(V(0, 0), V(4, 0)))
    tool = TapeMeasureTool()
    tool.on_click(_ctx(vp, 0, 0, snap=SimpleNamespace(kind="endpoint")))
    assert tool._edge is None


def test_nothing_under_the_cursor_still_measures():
    scene = Scene()
    vp = _Vp(scene, loose=None, grouped=None)
    tool = TapeMeasureTool()
    tool.on_click(_ctx(vp, 1, 1))
    assert tool._edge is None
    tool.on_click(_ctx(vp, 4, 1))
    assert not scene.guides
    assert tool._measured is not None
