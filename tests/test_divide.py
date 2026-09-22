# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""SketchUp's Divide (issue #63, @pacaeiro): a line or an arc into N equal
pieces; and the undo cap (issue #56)."""
from __future__ import annotations

from PySide6.QtGui import QVector3D

from core.edits import divide_edges
from core.history import History, SnapshotMutation, AddEdgeCommand
from core.mesh import Mesh
from core.scene import Scene


def V(x, y, z=0.0):
    return QVector3D(float(x), float(y), float(z))


def test_a_line_is_divided_into_equal_pieces():
    m = Mesh()
    e = m.add_edge(V(0, 0), V(4, 0))
    assert divide_edges(m, [e], 4) == 3
    xs = sorted(round(v.position.x(), 6) for v in m.vertices)
    assert xs == [0.0, 1.0, 2.0, 3.0, 4.0]
    assert len(m.edges) == 4


def test_a_face_edge_divided_keeps_the_face_whole():
    m = Mesh()
    f = m.add_face([V(0, 0), V(4, 0), V(4, 2), V(0, 2)])
    bottom = next(e for e in m.edges if abs(e.a.y()) < 1e-9 and abs(e.b.y()) < 1e-9)
    divide_edges(m, [bottom], 2)
    assert len(m.faces) == 1 and len(f.vertices) == 5


def test_an_arc_is_divided_along_its_chain_and_stays_one_curve():
    m = Mesh()
    pts = [V(0, 0), V(1, 0.5), V(2, 0.8), V(3, 0.5), V(4, 0)]      # a polyline "arc"
    for a, b in zip(pts, pts[1:]):
        m.add_edge(a, b)
    m.tag_curve(pts, closed=False)
    seed = next(e for e in m.edges if e.curve is not None)
    cid = seed.curve
    total = sum((b - a).length() for a, b in zip(pts, pts[1:]))
    divide_edges(m, [seed], 3)
    curve = [e for e in m.edges if e.curve == cid]
    assert len(curve) == 6                                          # 4 facets + 2 cuts
    # the two cuts sit at a third and two thirds of the length
    lengths = sorted((e.b - e.a).length() for e in curve)
    assert abs(sum(lengths) - total) < 1e-9


def test_divide_is_one_undo_step():
    scene = Scene()
    hist = History(scene)
    hist.execute(AddEdgeCommand(V(0, 0), V(3, 0)))
    e = scene.mesh.edges[0]
    hist.execute(SnapshotMutation(lambda sc: divide_edges(sc.mesh, [e], 3)))
    assert len(scene.mesh.edges) == 3
    hist.undo()
    assert len(scene.mesh.edges) == 1


def test_the_undo_stack_is_capped():
    scene = Scene()
    hist = History(scene)
    hist.max_steps = 3
    for i in range(6):
        hist.execute(AddEdgeCommand(V(i, 0), V(i + 1, 0)))
    assert len(hist.undo_stack) == 3
    hist.max_steps = 0                                              # unlimited
    for i in range(6, 10):
        hist.execute(AddEdgeCommand(V(i, 0), V(i + 1, 0)))
    assert len(hist.undo_stack) == 7
