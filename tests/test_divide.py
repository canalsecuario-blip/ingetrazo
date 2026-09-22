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


def _curves(m):
    """``{curve id: [edges]}`` of the mesh."""
    out: dict = {}
    for e in m.edges:
        if e.curve is not None:
            out.setdefault(e.curve, []).append(e)
    return out


def _length(edges):
    return sum((e.b - e.a).length() for e in edges)


def test_an_arc_divided_becomes_n_independent_arcs_of_equal_length():
    # SketchUp: a curve divided in 3 is three arcs, each its own contour.
    m = Mesh()
    pts = [V(0, 0), V(1, 0.5), V(2, 0.8), V(3, 0.5), V(4, 0)]      # a polyline "arc"
    for a, b in zip(pts, pts[1:]):
        m.add_edge(a, b)
    m.tag_curve(pts, closed=False)
    seed = next(e for e in m.edges if e.curve is not None)
    total = _length(m.edges)
    assert divide_edges(m, [seed], 3) == 2
    curves = _curves(m)
    assert len(curves) == 3
    assert sum(len(v) for v in curves.values()) == 6              # 4 facets + 2 cuts
    for edges in curves.values():
        assert abs(_length(edges) - total / 3) < 1e-6      # QVector3D is float32
    # every facet keeps the curve's softness
    assert all(e.soft == seed.soft for es in curves.values() for e in es)


def test_a_facet_running_against_the_walk_is_cut_at_the_right_place():
    # The middle facet is added b→a, so its v0→v1 runs against the chain;
    # the marks must still land at 1/3 and 2/3 of the chain, not mirrored.
    m = Mesh()
    m.add_edge(V(0, 0), V(1, 0))
    m.add_edge(V(2, 0), V(1, 0))                                     # reversed
    m.add_edge(V(2, 0), V(3, 0))
    m.tag_curve([V(0, 0), V(1, 0), V(2, 0), V(3, 0)], closed=False)
    seed = next(e for e in m.edges if abs(e.a.x()) < 1e-9 or abs(e.b.x()) < 1e-9)
    divide_edges(m, [seed], 2)
    xs = sorted(round(v.position.x(), 6) for v in m.vertices)
    assert xs == [0.0, 1.0, 1.5, 2.0, 3.0]
    curves = _curves(m)
    assert len(curves) == 2
    assert all(abs(_length(es) - 1.5) < 1e-6 for es in curves.values())


def test_a_circle_divided_where_the_marks_fall_on_facet_vertices():
    # 24 facets divided in 6: every mark sits on an existing vertex, so
    # nothing is cut, yet the circle parts into six 4-facet arcs.
    import math
    m = Mesh()
    pts = [V(math.cos(2 * math.pi * i / 24), math.sin(2 * math.pi * i / 24))
           for i in range(24)]
    for i in range(24):
        m.add_edge(pts[i], pts[(i + 1) % 24])
    m.tag_curve(pts, closed=True)
    seed = m.edges[0]
    assert divide_edges(m, [seed], 6) == 0
    curves = _curves(m)
    assert len(curves) == 6
    assert sorted(len(es) for es in curves.values()) == [4] * 6
    assert len(m.edges) == 24


def test_a_circle_divided_in_four_is_four_quarter_arcs():
    import math
    m = Mesh()
    pts = [V(math.cos(2 * math.pi * i / 18), math.sin(2 * math.pi * i / 18))
           for i in range(18)]
    for i in range(18):
        m.add_edge(pts[i], pts[(i + 1) % 18])
    m.tag_curve(pts, closed=True)
    total = _length(m.edges)
    divide_edges(m, [m.edges[5]], 4)                               # 18/4: two cuts inside facets
    curves = _curves(m)
    assert len(curves) == 4
    for es in curves.values():
        assert abs(_length(es) - total / 4) < 1e-6
    # and a face bounded by the circle survives whole
    m2 = Mesh()
    m2.add_face(pts)
    m2.tag_curve(pts, closed=True)
    f = m2.faces[0]
    divide_edges(m2, [m2.edges[0]], 4)
    assert len(m2.faces) == 1 and len(f.vertices) == 20


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
