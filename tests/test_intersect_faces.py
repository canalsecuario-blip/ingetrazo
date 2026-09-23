# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""SketchUp's Edit ▸ Intersect Faces (core/intersect.py): edges where faces
cross, added to the context being edited."""
from __future__ import annotations

import math

from PySide6.QtGui import QVector3D

from core import intersect as X
from core.edits import build_add_edges
from core.group import Group
from core.history import History
from core.mesh import Mesh
from core.scene import Scene
from core.solids import solid_report

RED, BLUE = [1.0, 0.0, 0.0], [0.0, 0.0, 1.0]


def V(x, y, z=0.0):
    return QVector3D(float(x), float(y), float(z))


def _box(x0, y0, z0, x1, y1, z1, color):
    m = Mesh()
    P = V
    for pts in (
        [P(x0, y0, z0), P(x0, y1, z0), P(x1, y1, z0), P(x1, y0, z0)],
        [P(x0, y0, z1), P(x1, y0, z1), P(x1, y1, z1), P(x0, y1, z1)],
        [P(x0, y0, z0), P(x1, y0, z0), P(x1, y0, z1), P(x0, y0, z1)],
        [P(x1, y0, z0), P(x1, y1, z0), P(x1, y1, z1), P(x1, y0, z1)],
        [P(x1, y1, z0), P(x0, y1, z0), P(x0, y1, z1), P(x1, y1, z1)],
        [P(x0, y1, z0), P(x0, y0, z0), P(x0, y0, z1), P(x0, y1, z1)],
    ):
        m.add_face(pts).attrs["color"] = list(color)
    return Group(m, name="box")


def _length(segs):
    return sum((q - p).length() for p, q in segs)


def test_two_crossing_squares_meet_on_one_segment():
    m = Mesh()
    a = m.add_face([V(0, 0), V(2, 0), V(2, 2), V(0, 2)])                 # z = 0
    b = m.add_face([V(1, -1, -1), V(1, 3, -1), V(1, 3, 1), V(1, -1, 1)])  # x = 1
    segs = X.cross(X.world_polys(a), X.world_polys(b))
    assert len(segs) == 1 and math.isclose(_length(segs), 2.0, abs_tol=1e-6)


def test_a_hole_interrupts_the_crossing():
    m = Mesh()
    a = m.add_face([V(0, 0), V(4, 0), V(4, 4), V(0, 4)],
                   [[V(1, 1), V(1, 3), V(3, 3), V(3, 1)]])
    b = m.add_face([V(2, -1, -1), V(2, 5, -1), V(2, 5, 1), V(2, -1, 1)])
    segs = X.cross(X.world_polys(a), X.world_polys(b))
    assert len(segs) == 2 and math.isclose(_length(segs), 2.0, abs_tol=1e-6)


def test_coplanar_faces_do_not_cross():
    m = Mesh()
    a = m.add_face([V(0, 0), V(2, 0), V(2, 2), V(0, 2)])
    b = m.add_face([V(1, 1), V(3, 1), V(3, 3), V(1, 3)])
    assert X.cross(X.world_polys(a), X.world_polys(b)) == []


def test_with_model_two_groups_leave_the_edges_outside_them():
    scene = Scene()
    hist = History(scene)
    a, b = _box(0, 0, 0, 2, 2, 2, RED), _box(1, 1, 1, 3, 3, 3, BLUE)
    scene.groups += [a, b]
    scene.selection = {a}
    segs = X.segments_for(scene, X.WITH_MODEL)
    assert len(segs) == 6 and math.isclose(_length(segs), 6.0, abs_tol=1e-6)
    faces_a = len(a.mesh.faces)
    hist.execute(build_add_edges(scene, segs, detect_faces=True))
    assert len(scene.mesh.edges) == 6                 # loose, as in SketchUp
    assert len(a.mesh.faces) == faces_a               # the groups untouched
    hist.undo()
    assert not scene.mesh.edges


def test_with_model_splits_the_loose_faces_a_group_runs_through():
    scene = Scene()
    hist = History(scene)
    for f in _box(0, 0, 0, 2, 2, 2, RED).mesh.faces:
        scene.mesh.add_face(f.vertices)
    scene.groups.append(_box(1, -1, 1, 1.5, 3, 3, BLUE))   # a bar through
    scene.selection = set(scene.mesh.faces)
    segs = X.segments_for(scene, X.WITH_MODEL)
    hist.execute(build_add_edges(scene, segs, detect_faces=True))
    assert len(scene.mesh.faces) == 10                # 2 sides + top split
    assert solid_report(scene.mesh)[0]                # still closed


def test_with_selection_ignores_what_is_not_selected():
    scene = Scene()
    a, b = _box(0, 0, 0, 2, 2, 2, RED), _box(1, 1, 1, 3, 3, 3, BLUE)
    c = _box(1, -1, 1, 1.5, 3, 3, BLUE)
    scene.groups += [a, b, c]
    scene.selection = {a, b}
    only_ab = X.segments_for(scene, X.WITH_SELECTION)
    scene.selection = {a}
    with_model = X.segments_for(scene, X.WITH_MODEL)
    assert len(only_ab) == 6
    assert len(with_model) > len(only_ab)             # the bar counts too
