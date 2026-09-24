# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""Split into Pieces: a group regrouped by the solids that do not touch.

A model file's own parts are often surface fragments cut by material (a Sweet
Home 3D bar stool: 43 groups, five real pieces); connectivity is what finds
the pieces a person would pick up."""
from __future__ import annotations

from PySide6.QtGui import QMatrix4x4, QVector3D

from core.group import Group, world_mesh
from core.history import SplitIntoPiecesCommand
from core.mesh import Mesh
from core.pieces import connected_parts, split_into_pieces
from core.scene import Scene

_QUADS = ((0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4),
          (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5))


def _corners(x0: float, z0: float = 0.0) -> list:
    return [QVector3D(x0 + dx, dy, z0 + dz) for dz in (0, 1) for dy in (0, 1)
            for dx in (0, 1)]


def _cube(mesh: Mesh, x0: float, z0: float = 0.0, quads=_QUADS) -> None:
    c = _corners(x0, z0)
    for q in quads:
        mesh.add_face([c[k] for k in q])


def _points(group) -> set:
    return {(round(v.position.x(), 5), round(v.position.y(), 5),
             round(v.position.z(), 5)) for v in world_mesh(group).vertices}


def test_two_separate_solids_become_two_pieces():
    mesh = Mesh()
    _cube(mesh, 0)
    _cube(mesh, 5)
    parts = connected_parts(mesh)
    assert [len(f) for f, _e in parts] == [6, 6]
    pieces = split_into_pieces(Group(mesh))
    assert [p.name for p in pieces] == ["Piece 1", "Piece 2"]
    assert all(len(p.mesh.faces) == 6 for p in pieces)


def test_fragments_across_children_join_into_the_piece_they_are():
    """Half a cube in one child, the other half in another — the way a file
    splits a part by material. Together they are one piece."""
    a, b = Mesh(), Mesh()
    _cube(a, 0, quads=_QUADS[:3])
    _cube(b, 0, quads=_QUADS[3:])
    halves = []
    for m in (a, b):
        g = Group(m)
        g.xform = QMatrix4x4()
        halves.append(g)
    stool = Group()
    stool.adopt(halves)
    pieces = split_into_pieces(stool)
    assert len(pieces) == 1
    assert len(pieces[0].mesh.faces) == 6


def test_a_single_piece_has_nothing_to_split():
    mesh = Mesh()
    _cube(mesh, 0)
    assert split_into_pieces(Group(mesh)) == []


def test_splitting_twice_changes_nothing():
    mesh = Mesh()
    _cube(mesh, 0)
    _cube(mesh, 5)
    group = Group(mesh)
    scene = Scene()
    scene.groups.append(group)
    SplitIntoPiecesCommand(group, split_into_pieces(group)).do(scene)
    assert split_into_pieces(group) == []


def test_touching_solids_that_share_vertices_read_as_one():
    """The documented limit: welded at a shared face, two cubes are one
    piece to connectivity, as they are to the eye on a welded mesh."""
    mesh = Mesh()
    _cube(mesh, 0)
    _cube(mesh, 0, z0=1)
    assert len(connected_parts(mesh)) == 1


def test_the_split_keeps_the_geometry_where_it_was_and_undoes():
    mesh = Mesh()
    _cube(mesh, 0)
    _cube(mesh, 5)
    mesh.faces[0].attrs["color"] = [0.8, 0.1, 0.1]
    group = Group(mesh, name="stool")
    place = QMatrix4x4()
    place.translate(QVector3D(3, 4, 0))
    place.rotate(30, 0, 0, 1)
    group.xform = place                    # a placed component
    scene = Scene()
    scene.groups.append(group)
    before = _points(group)

    cmd = SplitIntoPiecesCommand(group, split_into_pieces(group))
    cmd.do(scene)
    assert scene.groups == [group] and group.name == "stool"
    assert group.xform == place            # still placed where it was
    assert not group.mesh.faces and len(group.children) == 2
    assert _points(group) == before
    painted = [f for k in group.children for f in k.mesh.faces
               if f.attrs.get("color")]
    assert len(painted) == 1               # the paint travelled

    cmd.undo(scene)
    assert group.mesh is mesh and not group.children
    assert group.xform == place


def test_edge_flags_travel_with_the_piece():
    mesh = Mesh()
    _cube(mesh, 0)
    _cube(mesh, 5)
    for e in mesh.edges[:2]:
        e.hidden = True
        e.soft = True
    pieces = split_into_pieces(Group(mesh))
    assert sum(e.hidden for p in pieces for e in p.mesh.edges) == 2
    assert sum(e.soft for p in pieces for e in p.mesh.edges) == 2
