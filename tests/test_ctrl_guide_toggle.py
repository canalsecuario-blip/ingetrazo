# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""Ctrl on the Tape and the Protractor: measure, or measure AND mark (#29).

@pacaeiro: «In SK we have a CTRL toggle in the Protactor and Tape commands,
and that toggle enables or disables the creation of guidelines in the
commands, allowing just to measure a distance or angle, or to create a
Guideline, if necessary. It would be handy to have that!»

Both tools left a guide behind whether you wanted one or not, so measuring
meant cleaning up afterwards. Ctrl is a MODE, not a per-click modifier; it
survives between operations and resets when the tool is picked up, the way
SketchUp's does.

On the TAPE it cycles three ways, not two — its status bar spells them out
(Marco's screenshot, 2026-09-17): «Ctrl = Líneas guía del ciclo / Puntos
guía / Medida». Guide POINTS were a mode we did not have at all: the
entity exists (a Guide with no direction) and the Tape never made one.
The Protractor has only guides on/off; it cannot make a point.

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


def test_ctrl_cycles_the_tape_through_the_three_sketchup_modes():
    scene = Scene()
    vp = _Vp(scene, _edge(V(0, 0), V(4, 0)))
    tool = TapeMeasureTool()
    assert tool._mode == "line"
    for expected in ("point", "measure", "line"):
        assert tool.on_key(vp, Qt.Key_Control, Qt.NoModifier)
        assert tool._mode == expected


def test_the_middle_mode_drops_a_guide_POINT():
    scene = Scene()
    vp = _Vp(scene, _edge(V(0, 0), V(4, 0)))
    tool = TapeMeasureTool()
    tool.on_key(vp, Qt.Key_Control, Qt.NoModifier)     # → points
    tool.on_click(_ctx(vp, 1, 0))
    tool.on_click(_ctx(vp, 1, 2))
    assert len(scene.guides) == 1
    g = scene.guides[0]
    assert not g.is_line, "a POINT, not a line"
    assert abs(g.point.y() - 2.0) < 1e-6


def test_a_typed_distance_places_the_point_exactly():
    scene = Scene()
    vp = _Vp(scene, _edge(V(0, 0), V(4, 0)))
    tool = TapeMeasureTool()
    tool.on_key(vp, Qt.Key_Control, Qt.NoModifier)     # → points
    tool.on_click(_ctx(vp, 0, 0))
    tool.on_hover(_ctx(vp, 0, 1))                      # pointing up +Y
    assert tool.on_value(vp, 2.5)
    assert len(scene.guides) == 1
    assert abs(scene.guides[0].point.y() - 2.5) < 1e-6


def test_ctrl_turns_the_tape_into_a_plain_ruler():
    scene = Scene()
    vp = _Vp(scene, _edge(V(0, 0), V(4, 0)))
    tool = TapeMeasureTool()
    tool.on_key(vp, Qt.Key_Control, Qt.NoModifier)     # → points
    tool.on_key(vp, Qt.Key_Control, Qt.NoModifier)     # → measure
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
        while tool._guides:                    # walk to the measure-only mode
            tool.on_key(vp, Qt.Key_Control, Qt.NoModifier)
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
        while tool._guides:
            tool.on_key(vp, Qt.Key_Control, Qt.NoModifier)
        assert tool.cursor_plus is False, type(tool).__name__


def test_the_tape_toggle_survives_the_operation():
    """A mode, not a per-click modifier."""
    scene = Scene()
    vp = _Vp(scene, _edge(V(0, 0), V(4, 0)))
    tool = TapeMeasureTool()
    tool.on_key(vp, Qt.Key_Control, Qt.NoModifier)   # → points
    tool.on_key(vp, Qt.Key_Control, Qt.NoModifier)   # → measure
    tool.on_click(_ctx(vp, 1, 0))
    tool.on_click(_ctx(vp, 1, 2))
    tool.on_click(_ctx(vp, 1, 0))          # a second measurement
    tool.on_click(_ctx(vp, 1, 3))
    assert scene.guides == []
    tool.on_key(vp, Qt.Key_Control, Qt.NoModifier)   # …until it comes round
    assert tool._mode == "line"


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


def test_the_status_bar_keeps_the_ctrl_clause_up():
    """SketchUp keeps its modifiers on screen the whole time the tool is
    active — «Ctrl = Líneas guía del ciclo/Puntos guía/Medida» — instead of
    flashing them once. A flash says what just happened; this says what you
    can do and which way it is set (Marco, 2026-09-17)."""
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])
    from views.main_window import MainWindow

    win = MainWindow()
    win.show()
    app.processEvents()
    vp = win.viewport
    try:
        win._activate_tool("tape")
        tool = vp.active_tool
        # the active mode is bracketed, and it MOVES with Ctrl — read off
        # the status bar itself, with no mouse movement in between
        seen = []
        for _ in range(3):
            seen.append(win.status_hint)
            tool.on_key(vp, Qt.Key_Control, Qt.NoModifier)
        assert all("Ctrl =" in t for t in seen)
        assert len(set(seen)) == 3, "the clause must change with the mode"
        assert seen[0].index("[") < seen[1].index("[") < seen[2].index("[")
    finally:
        win._saved_version = vp.scene.version
        win.close()


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
