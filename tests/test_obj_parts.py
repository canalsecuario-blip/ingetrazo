# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""An OBJ written as parts imports as parts, and Explode sets them free.

A furniture OBJ names its pieces with ``g``/``o`` statements — a Sweet Home
3D bar stool is 43 of them. They used to be read past and the whole model
fused into one mesh, so the parts a user wanted to select, list or pull apart
were gone the moment the file was opened."""
from __future__ import annotations

from PySide6.QtGui import QMatrix4x4, QVector3D

from core.group import world_mesh
from core.history import ExplodeGroupCommand
from core.scene import Scene
from formats.obj import load_obj


def _cube(x0: float, z0: float, base: int) -> str:
    """Eight vertices and six quads of a 1 m cube at (x0, 0, z0)."""
    pts = [(x0 + dx, dy, z0 + dz) for dz in (0, 1) for dy in (0, 1)
           for dx in (0, 1)]
    quads = [(1, 3, 4, 2), (5, 6, 8, 7), (1, 2, 6, 5),
             (3, 7, 8, 4), (1, 5, 7, 3), (2, 4, 8, 6)]
    lines = [f"v {x} {y} {z}" for x, y, z in pts]
    lines += ["f " + " ".join(str(base + i) for i in q) for q in quads]
    return "\n".join(lines)


def _write(tmp_path, body: str):
    p = tmp_path / "piece.obj"
    p.write_text(body + "\n")
    return p


def _two_stacked(tmp_path, names=("seat", "leg")):
    """Two cubes, one resting on the other: they share a whole face."""
    return _write(tmp_path, f"g {names[0]}\n{_cube(0, 1, 0)}\n"
                            f"g {names[1]}\n{_cube(0, 0, 8)}")


def test_groups_in_the_file_become_named_children(tmp_path):
    scene = Scene()
    load_obj(scene, _two_stacked(tmp_path))
    assert not scene.mesh.faces            # nothing spilled into loose geometry
    assert len(scene.groups) == 1
    stool = scene.groups[0]
    assert stool.name == "piece"
    assert [k.name for k in stool.children] == ["seat", "leg"]
    assert stool.is_instance()             # a container is always an instance


def test_touching_parts_are_not_welded_together(tmp_path):
    """The seat rests on the leg; fused as one mesh their shared face would
    dissolve. Fused piece by piece, each is still a closed cube."""
    scene = Scene()
    load_obj(scene, _two_stacked(tmp_path))
    for kid in scene.groups[0].children:
        assert len(kid.mesh.faces) == 6


def test_numbered_groups_read_as_parts(tmp_path):
    scene = Scene()
    load_obj(scene, _two_stacked(tmp_path, names=("1", "2")))
    assert [k.name for k in scene.groups[0].children] == ["Part 1", "Part 2"]


def test_a_single_piece_file_imports_as_before(tmp_path):
    scene = Scene()
    load_obj(scene, _write(tmp_path, "g only\n" + _cube(0, 0, 0)))
    assert not scene.groups
    assert len(scene.mesh.faces) == 6


def test_explode_frees_the_parts_where_they_stood(tmp_path):
    scene = Scene()
    load_obj(scene, _two_stacked(tmp_path))
    stool = scene.groups[0]
    move = QMatrix4x4()
    move.translate(QVector3D(5, 2, 0))
    stool.xform = move * stool.xform       # placed somewhere, as a user would
    before = set((round(v.position.x(), 6), round(v.position.y(), 6),
                  round(v.position.z(), 6))
                 for v in world_mesh(stool).vertices)

    cmd = ExplodeGroupCommand(stool)
    cmd.do(scene)
    assert stool not in scene.groups
    assert [g.name for g in scene.groups] == ["seat", "leg"]
    assert not scene.mesh.faces            # parts, not a heap of loose faces
    after = set((round(v.position.x(), 6), round(v.position.y(), 6),
                 round(v.position.z(), 6))
                for g in scene.groups for v in world_mesh(g).vertices)
    assert after == before

    cmd.undo(scene)
    assert scene.groups == [stool]
    assert [k.name for k in stool.children] == ["seat", "leg"]
    assert all(k.xform == QMatrix4x4() for k in stool.children)
