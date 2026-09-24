# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""The Parts tray: a component's parts, measured like a cut list."""
from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QMatrix4x4, QVector3D
from PySide6.QtWidgets import QApplication

from core.group import Group
from core.mesh import Mesh
from core.parts import (cut_list, cut_list_text, part_material,
                        part_points, part_rows, part_size)

_app = QApplication.instance() or QApplication([])

_QUADS = ((0, 2, 3, 1), (4, 5, 7, 6), (0, 1, 5, 4),
          (2, 6, 7, 3), (0, 4, 6, 2), (1, 3, 7, 5))


def _box(sx: float, sy: float, sz: float, at=(0.0, 0.0, 0.0),
         color=None) -> Mesh:
    mesh = Mesh()
    x0, y0, z0 = at
    c = [QVector3D(x0 + dx * sx, y0 + dy * sy, z0 + dz * sz)
         for dz in (0, 1) for dy in (0, 1) for dx in (0, 1)]
    for q in _QUADS:
        f = mesh.add_face([c[k] for k in q])
        if color is not None:
            f.attrs["color"] = list(color)
    return mesh


def _part(mesh: Mesh, name: str, xform=None) -> Group:
    g = Group(mesh, name=name)
    g.xform = xform if xform is not None else QMatrix4x4()
    return g


def _stool() -> Group:
    """A seat and two identical legs, one of them splayed."""
    splay = QMatrix4x4()
    splay.translate(QVector3D(0.5, 0, 0))
    splay.rotate(10, 0, 1, 0)
    kids = [_part(_box(0.40, 0.40, 0.03, color=(0.6, 0.4, 0.2)), "seat"),
            _part(_box(0.04, 0.04, 0.58, color=(0.6, 0.4, 0.2)), "leg A"),
            _part(_box(0.04, 0.04, 0.58, color=(0.6, 0.4, 0.2)), "leg B",
                  splay)]
    stool = Group(name="stool")
    stool.adopt(kids)
    return stool


def test_a_board_measures_on_its_own_axes():
    size = part_size(part_points(_part(_box(0.8, 0.3, 0.018), "board")))
    assert size == pytest.approx((0.8, 0.3, 0.018), abs=1e-6)


def test_a_splayed_leg_measures_along_its_length():
    """Along the stool's axes the leg at 30° is a fat diagonal; along its
    own it is the stick it is."""
    turn = QMatrix4x4()
    turn.rotate(30, 0, 1, 0)
    leg = _part(_box(0.04, 0.04, 0.58), "leg", turn)
    assert part_size(part_points(leg)) == pytest.approx((0.58, 0.04, 0.04),
                                                        abs=1e-5)


def test_the_material_is_the_one_covering_most_of_the_part():
    mesh = _box(1.0, 1.0, 0.02, color=(1, 0, 0))
    small = [f for f in mesh.faces if f.area() < 0.1]
    for f in small:                        # the four thin edges: 0.08 m²
        f.attrs["color"] = [0, 0, 1]
    assert part_material(_part(mesh, "top")) == "#ff0000"


def test_a_part_inherits_its_containers_paint_on_default_faces():
    part = _part(_box(0.5, 0.5, 0.5), "cube")
    part.material = {"color": [0, 1, 0]}
    assert part_material(part) == "#00ff00"


def test_identical_parts_are_one_cut_list_line():
    rows = part_rows(_stool())
    lines = cut_list(rows)
    assert [(ln["qty"], ln["names"]) for ln in lines] == [
        (2, ["leg A", "leg B"]), (1, ["seat"])]
    text = cut_list_text(lines, lambda m: f"{m * 1000:.0f}",
                         ["Qty", "Parts", "Material", "L", "W", "T"])
    assert text.splitlines()[1] == "2\tleg A, leg B\t#996633\t580\t40\t40"


def test_the_material_can_be_left_out_of_the_match():
    """A Sweet Home 3D model paints every fragment with its own image, so
    two identical legs never share a material there."""
    stool = _stool()
    for f in stool.children[2].mesh.faces:
        f.attrs["color"] = [0.1, 0.1, 0.1]
    assert [ln["qty"] for ln in cut_list(part_rows(stool))] == [1, 1, 1]
    merged = cut_list(part_rows(stool), by_material=False)
    assert [ln["qty"] for ln in merged] == [2, 1]
    assert merged[0]["material"] == "#996633, #1a1a1a"


def test_names_sort_naturally():
    kids = [_part(_box(0.1, 0.1, 0.1), f"Piece {n}") for n in (10, 2, 1)]
    holder = Group()
    holder.adopt(kids)
    assert cut_list(part_rows(holder))[0]["names"] == [
        "Piece 1", "Piece 2", "Piece 10"]


def _window_with(group):
    from views.main_window import MainWindow
    win = MainWindow()
    scene = win.viewport.scene
    scene.groups.append(group)
    scene.selection.clear()
    scene.selection.add(group)
    scene.version += 1
    return win, scene


def test_the_tray_lists_selects_hides_and_renames_parts():
    stool = _stool()
    win, scene = _window_with(stool)
    panel = win.tray.parts
    panel.refresh()
    tree = panel.tree
    assert tree.topLevelItemCount() == 3
    assert [tree.topLevelItem(i).text(0) for i in range(3)] == [
        "seat", "leg A", "leg B"]

    panel._on_clicked(tree.topLevelItem(1), 0)     # the Outliner's click
    assert scene.edit_group is stool
    assert scene.selection == {stool.children[1]}
    panel.refresh()
    assert tree.topLevelItemCount() == 3           # still listed inside it

    tree.topLevelItem(2).setCheckState(0, Qt.Unchecked)
    assert stool.children[2].hidden
    tree.topLevelItem(0).setText(0, "Seat board")
    assert stool.children[0].name == "Seat board"
    win.viewport.history.undo()
    assert stool.children[0].name == "seat"
    win.viewport.history.undo()
    assert not stool.children[2].hidden
    win._saved_version = scene.version


def test_a_plain_group_offers_to_split():
    mesh = _box(0.1, 0.1, 0.1)
    for f in _box(0.1, 0.1, 0.1, at=(1, 0, 0)).faces:
        mesh.add_face(f.vertices)
    group = Group(mesh, name="two blocks")
    win, scene = _window_with(group)
    panel = win.tray.parts
    panel.refresh()
    assert not panel.tree.isVisibleTo(panel)
    assert panel._split_btn.isEnabled()
    panel._on_split()
    assert [k.name for k in group.children] == ["Piece 1", "Piece 2"]
    assert panel.tree.topLevelItemCount() == 2
    win._saved_version = scene.version


def test_copy_cut_list_fills_the_clipboard():
    win, scene = _window_with(_stool())
    panel = win.tray.parts
    panel.refresh()
    panel._on_copy()
    lines = QApplication.clipboard().text().splitlines()
    assert len(lines) == 3 and lines[1].startswith("2\t")
    assert len(lines[0].split("\t")) == 6
    win._saved_version = scene.version
