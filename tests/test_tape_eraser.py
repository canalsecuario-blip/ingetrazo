# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""Tape Measure guides + Eraser strokes: entities, commands, .igz, erase flow."""
from __future__ import annotations

from PySide6.QtGui import QVector3D

from core.guide import Guide
from core.history import (
    AddGuideCommand,
    DeleteGuidesCommand,
    History,
)
from core.scene import Scene
from formats import igz


def V(x, y, z=0.0):
    return QVector3D(x, y, z)


# ---- Guide entity ---------------------------------------------------------------

def test_guide_line_segment_spans_both_ways():
    g = Guide(V(1, 2), V(1, 0, 0))
    a, b = g.segment()
    assert a.x() < 1 < b.x() and abs(a.y() - 2) < 1e-9 and abs(b.y() - 2) < 1e-9
    assert g.is_line
    # Snap duck-typing: .a/.b exist and differ.
    assert (g.b - g.a).length() > 1


def test_guide_point():
    g = Guide(V(3, 4))
    assert not g.is_line
    a, b = g.segment()
    assert (a - b).length() < 1e-9


def test_guide_commands_undo():
    scene = Scene()
    hist = History(scene)
    g = Guide(V(0, 0), V(0, 1, 0))
    hist.execute(AddGuideCommand(g))
    assert scene.guides == [g]
    hist.undo()
    assert scene.guides == []
    hist.redo()
    hist.execute(DeleteGuidesCommand([g]))
    assert scene.guides == []
    hist.undo()
    assert scene.guides == [g]


def test_guides_igz_round_trip(tmp_path):
    scene = Scene()
    scene.guides.append(Guide(V(1, 2, 0), V(0, 1, 0)))
    scene.guides.append(Guide(V(5, 5, 0)))            # a guide point
    path = tmp_path / "guides.igz"
    igz.save_scene(scene, path)
    loaded = Scene()
    igz.load_into(loaded, path)
    assert len(loaded.guides) == 2
    assert loaded.guides[0].is_line and not loaded.guides[1].is_line


def test_clear_resets_guides():
    scene = Scene()
    scene.guides.append(Guide(V(0, 0), V(1, 0, 0)))
    scene.clear()
    assert scene.guides == []


# ---- Eraser stroke (headless: mark + release) ------------------------------------

class _FakeViewport:
    """Just enough viewport for the eraser's release path."""

    def __init__(self, scene):
        self.scene = scene
        self.history = History(scene)

    def update(self):
        pass


def test_eraser_release_erases_marked_edges_one_undo():
    from tools.eraser import EraserTool
    from core.edits import build_add_edges
    scene = Scene()
    hist = History(scene)
    sq = [V(0, 0), V(2, 0), V(2, 2), V(0, 2)]
    hist.execute(build_add_edges(
        scene, [(sq[i], sq[(i + 1) % 4]) for i in range(4)], detect_faces=True))
    vp = _FakeViewport(scene)
    tool = EraserTool()
    tool._stroke = True
    tool.marked = set(scene.mesh.edges[:2])           # swept over two edges
    tool.on_release(vp)
    assert len(scene.mesh.edges) == 2                 # two gone in one step
    vp.history.undo()
    assert len(scene.mesh.edges) == 4                 # single undo restores


def test_eraser_release_erases_guides():
    from tools.eraser import EraserTool
    scene = Scene()
    g = Guide(V(0, 0), V(1, 0, 0))
    scene.guides.append(g)
    vp = _FakeViewport(scene)
    tool = EraserTool()
    tool._stroke = True
    tool.marked = {g}
    tool.on_release(vp)
    assert scene.guides == []


# ---- @pacaeiro, issue #46: the eraser takes groups and components whole

class _GroupPickingViewport(_FakeViewport):
    """The fake viewport with pickers: nothing loose under the cursor, a
    group there instead."""

    def __init__(self, scene, group):
        super().__init__(scene)
        self._group = group

    def pick_edge(self, x, y):
        return None

    def pick_group(self, x, y):
        return self._group

    def pick_guide(self, x, y):
        return None

    def pick_dimension(self, x, y):
        return None

    def pick_geopath(self, x, y):
        return None


def _grouped_square(scene):
    from PySide6.QtGui import QVector3D
    from core.group import Group
    from core.mesh import Mesh
    g = Group(Mesh(), name="caja")
    g.mesh.add_face([QVector3D(0, 0, 0), QVector3D(2, 0, 0),
                     QVector3D(2, 2, 0), QVector3D(0, 2, 0)])
    scene.groups.append(g)
    return g


def test_the_eraser_marks_the_group_under_the_cursor_and_erases_it_whole():
    """«ERASE tool cannot erase Groups nor Components, only raw edges and
    faces». A press over a group marks the group; the release deletes it
    in one undo step, and undo brings it back."""
    from tools.eraser import EraserTool
    scene = Scene()
    g = _grouped_square(scene)
    vp = _GroupPickingViewport(scene, g)
    tool = EraserTool()
    tool._stroke = True
    tool._mark(vp, 10.0, 10.0)
    assert tool.marked == {g}
    tool.on_release(vp)
    assert g not in scene.groups
    vp.history.undo()
    assert g in scene.groups


def test_shift_stroke_hides_the_group_instead():
    from tools.eraser import EraserTool
    scene = Scene()
    g = _grouped_square(scene)
    vp = _GroupPickingViewport(scene, g)
    tool = EraserTool()
    tool._stroke = True
    tool._hide = True
    tool._mark(vp, 10.0, 10.0)
    assert tool.marked == {g}
    tool.on_release(vp)
    assert g in scene.groups and getattr(g, "hidden", False) is True
    vp.history.undo()
    assert getattr(g, "hidden", False) is False


# ---- @pacaeiro, issue #66: «ERASE tool cannot erase Text»

class _LabelPickingViewport(_GroupPickingViewport):
    """A leader text's glyphs under the cursor, over a group."""

    def __init__(self, scene, group, label):
        super().__init__(scene, group)
        self._label = label

    def pick_text_label(self, x, y, rect_only=False):
        return self._label


def test_the_eraser_erases_a_leader_text_before_what_is_behind_it():
    from core.textlabel import TextLabel
    from tools.eraser import EraserTool
    scene = Scene()
    g = _grouped_square(scene)
    lab = TextLabel(V(1, 1), V(1, 1, 1), "Muro")
    scene.text_labels.append(lab)
    vp = _LabelPickingViewport(scene, g, lab)
    tool = EraserTool()
    tool._stroke = True
    tool._mark(vp, 10.0, 10.0)
    assert tool.marked == {lab}          # the glyphs outrank the group
    tool.on_release(vp)
    assert scene.text_labels == [] and g in scene.groups
    vp.history.undo()
    assert scene.text_labels == [lab]


def test_a_hide_stroke_leaves_texts_alone():
    from core.textlabel import TextLabel
    from tools.eraser import EraserTool
    scene = Scene()
    g = _grouped_square(scene)
    lab = TextLabel(V(1, 1), V(1, 1, 1), "Muro")
    scene.text_labels.append(lab)
    vp = _LabelPickingViewport(scene, g, lab)
    tool = EraserTool()
    tool._stroke = True
    tool._hide = True
    tool._mark(vp, 10.0, 10.0)
    assert lab not in tool.marked
