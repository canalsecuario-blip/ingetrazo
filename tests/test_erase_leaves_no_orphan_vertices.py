# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""Erasing takes the vertices with it (found live, 2026-09-18).

Marco lost his bearings during the inference test: a line had run 16 km out,
he deleted it, and then could not get back — zoom-to-extents had nothing to
find. Reading his scene through the bridge showed why, and it was not the
inference:

    malla suelta v/e/f   (9, 0, 0)
    vertex 0: (-14225.586, 8133.531, 0.000)  edges=0
    ...

Nine vertices, no edges, no faces, sixteen kilometres out. ``remove_edge``
detaches an edge from its endpoints and leaves the endpoints in the mesh, so
every erase since has left its vertices behind. They do not draw and
``bounds()`` ignores them, which is exactly why nobody noticed — but they go
into the ``.igz`` and they accumulate.

Undo is unaffected: the command snapshots the mesh before it touches
anything, and ``restore_state`` puts back the vertex list AND the position
registry.
"""
from __future__ import annotations

from PySide6.QtGui import QVector3D

from core.history import EraseSelectionCommand, History
from core.scene import Scene


def V(x, y, z=0.0):
    return QVector3D(float(x), float(y), float(z))


def _scene_with_a_loose_line():
    scene = Scene()
    m = scene.mesh
    m.add_edge(V(0, 0), V(3, 0))
    return scene


def test_erasing_a_loose_line_leaves_nothing_behind():
    scene = _scene_with_a_loose_line()
    edge = scene.mesh.edges[0]
    History(scene).execute(EraseSelectionCommand([edge]))
    assert scene.mesh.edges == []
    assert scene.mesh.vertices == [], "the endpoints must go too"


def test_a_vertex_still_used_by_a_face_survives():
    """The guard that keeps this from being destructive: a face holds real
    Vertex objects, so pruning by 'has no edges' alone would gut it."""
    scene = Scene()
    m = scene.mesh
    m.add_face([V(0, 0), V(2, 0), V(2, 2), V(0, 2)])
    suelta = m.add_edge(V(5, 5), V(7, 5))
    History(scene).execute(EraseSelectionCommand([suelta]))
    assert len(m.faces) == 1
    assert len(m.vertices) == 4, "the square keeps its four corners"


def test_undo_brings_the_vertices_back():
    scene = _scene_with_a_loose_line()
    history = History(scene)
    history.execute(EraseSelectionCommand([scene.mesh.edges[0]]))
    history.undo()
    assert len(scene.mesh.edges) == 1
    assert len(scene.mesh.vertices) == 2


def test_the_position_registry_lets_go_as_well():
    """A stale registry entry is worse than a stray vertex: the next point
    drawn there would weld to an object no longer in the mesh."""
    scene = _scene_with_a_loose_line()
    m = scene.mesh
    History(scene).execute(EraseSelectionCommand([m.edges[0]]))
    revived = m.vertex(V(0, 0))
    assert revived in m.vertices
    assert m.vertex_at(V(3, 0)) is None


def test_erasing_a_face_takes_its_corners():
    scene = Scene()
    m = scene.mesh
    m.add_face([V(0, 0), V(2, 0), V(2, 2), V(0, 2)])
    History(scene).execute(
        EraseSelectionCommand(list(m.edges), [m.faces[0]]))
    assert m.faces == []
    assert m.vertices == []
