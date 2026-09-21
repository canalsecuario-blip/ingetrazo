# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""Offset on EDGES (issue #40, @pacaeiro): the status bar promised «Click a
face, or connected edges, to offset» and only faces worked. Now a click on
an edge takes its connected run (open polyline or closed loop), and edges
selected before picking the tool up are the run — SketchUp's two ways."""
from __future__ import annotations

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QVector3D

from core.history import History
from core.offset import offset_chain
from core.scene import Scene
from tools.base import ToolContext
from tools.offset import OffsetTool, _run_from_edge, _run_from_edges


def V(x, y, z=0.0):
    return QVector3D(float(x), float(y), float(z))


class _Vp:
    """Enough viewport for the tool: no face under the cursor, the edge we
    say, no screen ray (the reference falls to the first segment)."""

    def __init__(self, scene, edge=None):
        self.scene = scene
        self.history = History(scene)
        self.edge = edge
        self.flashed: list = []

    def update(self):
        pass

    def set_hover(self, e):
        pass

    def flash_status(self, text, *a, **k):
        self.flashed.append(text)

    def pick_face(self, x, y):
        return None

    def pick_edge(self, x, y):
        return self.edge

    def _pixel_to_ray(self, x, y):
        return None, None


def _ctx(vp, world=V(0, 0)):
    return ToolContext(viewport=vp, world=world, screen=QPointF(0, 0),
                       modifiers=Qt.NoModifier, snap=None)


def _keys(points):
    return {(round(p.x(), 3), round(p.y(), 3), round(p.z(), 3)) for p in points}


def _edge_keys(scene):
    return {frozenset((_keys([e.a]).pop(), _keys([e.b]).pop()))
            for e in scene.mesh.edges}


# ---- core -----------------------------------------------------------------

def test_offset_chain_slides_an_open_L_either_way():
    pts = [V(0, 0), V(2, 0), V(2, 2)]
    assert _keys(offset_chain(pts, V(0, 0, 1), 0.5)) == {(0, .5, 0), (1.5, .5, 0), (1.5, 2, 0)}
    assert _keys(offset_chain(pts, V(0, 0, 1), -0.5)) == {(0, -.5, 0), (2.5, -.5, 0), (2.5, 2, 0)}


def test_run_from_edge_walks_through_corners_and_stops_at_junctions():
    scene = Scene()
    m = scene.mesh
    e1 = m.add_edge(V(0, 0), V(2, 0))
    m.add_edge(V(2, 0), V(2, 2))
    m.add_edge(V(2, 2), V(4, 2))
    m.add_edge(V(2, 2), V(2, 4))                  # a junction at (2,2)
    points, closed = _run_from_edge(e1)
    assert not closed
    assert [_keys([p]).pop() for p in points] == [(0, 0, 0), (2, 0, 0), (2, 2, 0)]


def test_run_from_edges_orders_a_selection_and_tells_a_loop():
    scene = Scene()
    m = scene.mesh
    es = [m.add_edge(V(0, 0), V(2, 0)), m.add_edge(V(2, 2), V(0, 2)),
          m.add_edge(V(2, 0), V(2, 2)), m.add_edge(V(0, 2), V(0, 0))]
    points, closed = _run_from_edges(es)
    assert closed and len(points) == 4
    assert _run_from_edges(es[:2]) is None        # two separate pieces


# ---- tool -----------------------------------------------------------------

def test_clicking_an_edge_offsets_its_run():
    scene = Scene()
    m = scene.mesh
    e1 = m.add_edge(V(0, 0), V(2, 0))
    m.add_edge(V(2, 0), V(2, 2))
    vp = _Vp(scene, e1)
    tool = OffsetTool()
    tool.on_activate(vp)
    tool.on_hover(_ctx(vp))
    tool.on_click(_ctx(vp))                        # takes the L
    assert tool.dragging and tool._chain and not tool._closed
    assert tool.on_value(vp, 0.5) is True
    assert frozenset({(0, .5, 0), (1.5, .5, 0)}) in _edge_keys(scene)
    assert frozenset({(1.5, .5, 0), (1.5, 2, 0)}) in _edge_keys(scene)
    assert len(m.edges) == 4 and not scene.faces  # nothing deleted, no face
    vp.history.undo()
    assert len(m.edges) == 2


def test_edges_selected_first_arm_the_tool():
    scene = Scene()
    m = scene.mesh
    es = [m.add_edge(V(0, 0), V(2, 0)), m.add_edge(V(2, 0), V(2, 2))]
    scene.select(es)
    vp = _Vp(scene)
    tool = OffsetTool()
    tool.on_activate(vp)
    assert tool._armed and any("2 edges" in t for t in vp.flashed)
    tool.on_click(_ctx(vp))
    assert tool.dragging
    tool.on_value(vp, 0.25)
    assert len(m.edges) == 4


def test_a_straight_run_is_refused_with_a_reason():
    scene = Scene()
    m = scene.mesh
    e1 = m.add_edge(V(0, 0), V(2, 0))
    m.add_edge(V(2, 0), V(4, 0))
    vp = _Vp(scene, e1)
    tool = OffsetTool()
    tool.on_activate(vp)
    tool.on_hover(_ctx(vp))
    tool.on_click(_ctx(vp))
    assert not tool.dragging
    assert any("not in line" in t for t in vp.flashed)


def test_a_closed_loop_of_bare_edges_offsets_as_a_loop():
    scene = Scene()
    m = scene.mesh
    e1 = m.add_edge(V(0, 0), V(4, 0))
    m.add_edge(V(4, 0), V(4, 4))
    m.add_edge(V(4, 4), V(0, 4))
    m.add_edge(V(0, 4), V(0, 0))
    for f in list(scene.faces):                   # bare edges: no face
        m.remove_face(f) if hasattr(m, "remove_face") else None
    vp = _Vp(scene, e1)
    tool = OffsetTool()
    tool.on_activate(vp)
    tool.on_hover(_ctx(vp))
    tool.on_click(_ctx(vp))
    assert tool._closed
    tool.on_value(vp, 0.5)
    keys = _edge_keys(scene)
    assert frozenset({(.5, .5, 0), (3.5, .5, 0)}) in keys
    assert frozenset({(.5, 3.5, 0), (.5, .5, 0)}) in keys
