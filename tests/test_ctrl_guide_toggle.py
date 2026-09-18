# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""Ctrl on the Tape and the Protractor: measure, or measure AND mark (#29).

@pacaeiro: «In SK we have a CTRL toggle in the Protactor and Tape commands,
and that toggle enables or disables the creation of guidelines in the
commands, allowing just to measure a distance or angle, or to create a
Guideline, if necessary. It would be handy to have that!»

Both tools left a guide behind whether you wanted one or not, so measuring
meant cleaning up afterwards. Ctrl is a MODE, not a per-click modifier —
it survives between operations, the way SketchUp's does.

Rotate shares the Protractor's base and takes Ctrl for its own copy mode;
it never creates a guide, so it must keep it.
"""
from __future__ import annotations

from types import SimpleNamespace

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QVector3D

from core.history import History
from core.scene import Scene
from tools.base import ToolContext
from tools.protractor import ProtractorTool
from tools.rotate import RotateTool
from tools.tape import TapeMeasureTool


def V(x, y, z=0.0):
    return QVector3D(float(x), float(y), float(z))


class _Vp:
    def __init__(self, scene, edge=None):
        self.scene = scene
        self.history = History(scene)
        self._edge = edge
        self.flashed = []

    def update(self):
        pass

    def set_hover(self, *_a):
        pass

    def flash_status(self, text, *a, **k):
        self.flashed.append(text)

    def pick_edge(self, x, y):
        return self._edge

    def pick_edge_any(self, x, y):
        return self._edge

    def pick_guide(self, x, y):
        return None

    def pick_face(self, x, y):
        return None

    def pick_group(self, x, y):
        return None


def _ctx(vp, x, y, z=0.0):
    return ToolContext(viewport=vp, world=V(x, y, z), screen=QPointF(0, 0),
                       modifiers=Qt.NoModifier, snap=None)


def _edge(a, b):
    return SimpleNamespace(a=a, b=b, in_group=False)


# ── Tape ────────────────────────────────────────────────────────────────────

def test_the_tape_leaves_a_guide_by_default():
    scene = Scene()
    vp = _Vp(scene, _edge(V(0, 0), V(4, 0)))
    tool = TapeMeasureTool()
    tool.on_click(_ctx(vp, 1, 0))
    tool.on_click(_ctx(vp, 1, 2))
    assert len(scene.guides) == 1


def test_ctrl_turns_the_tape_into_a_plain_ruler():
    scene = Scene()
    vp = _Vp(scene, _edge(V(0, 0), V(4, 0)))
    tool = TapeMeasureTool()
    assert tool.on_key(vp, Qt.Key_Control, Qt.NoModifier)
    assert tool._guides is False
    tool.on_click(_ctx(vp, 1, 0))
    tool.on_click(_ctx(vp, 1, 2))
    assert scene.guides == [], "measure only: nothing left behind"
    assert tool._measured is not None, "…but it did measure"


def test_picking_the_tool_up_starts_in_guide_mode():
    """SketchUp's rule: the + «appears or disappears depending on whether
    you tapped Ctrl SINCE YOU PICKED UP THE TOOL». Ours stayed off for
    good, so after one measure-only reading the guides looked broken —
    Marco hit it straight away: «solo funciona con ctrl»."""
    scene = Scene()
    vp = _Vp(scene, _edge(V(0, 0), V(4, 0)))
    for tool in (TapeMeasureTool(), ProtractorTool()):
        tool.on_key(vp, Qt.Key_Control, Qt.NoModifier)
        assert tool._guides is False
        tool.on_activate(vp)
        assert tool._guides is True, type(tool).__name__


def test_the_cursor_says_which_mode_it_is_in():
    """The + beside the cursor is the ENTIRE interface of this toggle in
    SketchUp; without it the mode is invisible until after the click."""
    scene = Scene()
    vp = _Vp(scene)
    for tool in (TapeMeasureTool(), ProtractorTool()):
        tool.on_activate(vp)
        assert tool.cursor_plus is True, type(tool).__name__
        tool.on_key(vp, Qt.Key_Control, Qt.NoModifier)
        assert tool.cursor_plus is False, type(tool).__name__


def test_the_tape_toggle_survives_the_operation():
    """A mode, not a per-click modifier."""
    scene = Scene()
    vp = _Vp(scene, _edge(V(0, 0), V(4, 0)))
    tool = TapeMeasureTool()
    tool.on_key(vp, Qt.Key_Control, Qt.NoModifier)
    tool.on_click(_ctx(vp, 1, 0))
    tool.on_click(_ctx(vp, 1, 2))
    tool.on_click(_ctx(vp, 1, 0))          # a second measurement
    tool.on_click(_ctx(vp, 1, 3))
    assert scene.guides == []
    tool.on_key(vp, Qt.Key_Control, Qt.NoModifier)   # …until it is turned back
    assert tool._guides is True


# ── Protractor ──────────────────────────────────────────────────────────────

def _measure(vp, tool, deg=45.0):
    import math
    tool.on_click(_ctx(vp, 0, 0))                     # the vertex
    tool.on_click(_ctx(vp, 2, 0))                     # the base arm
    r = 2.0
    tool.on_click(_ctx(vp, r * math.cos(math.radians(deg)),
                       r * math.sin(math.radians(deg))))


def test_the_protractor_leaves_a_guide_by_default():
    scene = Scene()
    vp = _Vp(scene)
    _measure(vp, ProtractorTool())
    assert len(scene.guides) == 1


def test_ctrl_turns_the_protractor_into_a_plain_protractor():
    scene = Scene()
    vp = _Vp(scene)
    tool = ProtractorTool()
    assert tool.on_key(vp, Qt.Key_Control, Qt.NoModifier)
    assert tool._guides is False
    _measure(vp, tool)
    assert scene.guides == [], "measure only: nothing left behind"
    assert any("°" in m for m in vp.flashed), "…but it reported the angle"


def test_ctrl_still_means_COPY_on_rotate():
    """Rotate shares the base and never creates a guide: its Ctrl is the
    copy modifier and must not be taken over."""
    scene = Scene()
    scene.mesh.add_face([V(2, 0), V(3, 0), V(3, 1), V(2, 1)])
    scene.selection = [scene.mesh.faces[0]]
    vp = _Vp(scene)
    tool = RotateTool()
    assert tool.on_key(vp, Qt.Key_Control, Qt.NoModifier)
    assert tool._copy is True
    assert not hasattr(tool, "_guides") or tool._guides is True
