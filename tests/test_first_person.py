# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""First Person (tools/walkthrough.py) — a walkthrough mode that plays like
a game, next to SketchUp's Walk and not instead of it: W/A/S/D move, Q/E go
down/up, Shift runs, Alt goes through walls, and a mouse drag (right button,
or left) turns the head.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QPoint, Qt
from PySide6.QtGui import QAction, QVector3D
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

_app = QApplication.instance() or QApplication([])

from tools import walkthrough as wt
from tools.walkthrough import FirstPersonTool, WalkTool


@pytest.fixture(autouse=True)
def _default_eye_height(monkeypatch):
    monkeypatch.setattr(wt, "eye_height", lambda: 1.68)
    monkeypatch.setattr(wt, "set_eye_height", lambda v: None)


def _room(vp):
    """A 6 × 6 m room, walls 3 m tall, on the ground."""
    mesh = vp.scene.mesh
    floor = [QVector3D(0, 0, 0), QVector3D(6, 0, 0), QVector3D(6, 6, 0),
             QVector3D(0, 6, 0)]
    mesh.add_face(floor)
    for a, b in zip(floor, floor[1:] + floor[:1]):
        mesh.add_face([a, b, QVector3D(b.x(), b.y(), 3.0),
                       QVector3D(a.x(), a.y(), 3.0)])
    vp.scene.version += 1
    vp.update()
    _app.processEvents()


@pytest.fixture
def win():
    from views.main_window import MainWindow
    w = MainWindow()
    w.show()
    w.resize(1200, 800)
    _app.processEvents()
    _room(w.viewport)
    # Standing in the middle of the room, looking north (+Y).
    w.viewport.camera.perspective = True
    w.viewport.camera.look_from(QVector3D(3, 3, 1.68), QVector3D(0, 1, 0))
    yield w
    w._saved_version = w.viewport.scene.version
    w.close()


def _tool(win) -> FirstPersonTool:
    win._activate_tool("first_person")
    tool = win.viewport.active_tool
    assert isinstance(tool, FirstPersonTool)
    return tool


def _walk(tool, vp, keys, seconds=0.5, mods=Qt.NoModifier):
    """Move for ``seconds`` with ``keys`` held; the eye's displacement."""
    before = vp.camera.eye()
    dt = FirstPersonTool.TICK_MS / 1000.0
    for _ in range(int(round(seconds / dt))):
        tool.step(vp, set(keys), dt, mods)
    return vp.camera.eye() - before


# ---- Moving ---------------------------------------------------------------------

def test_w_walks_forward_and_s_back(win):
    vp = win.viewport
    tool = _tool(win)
    d = _walk(tool, vp, {Qt.Key_W})
    assert d.y() > 0.5 and abs(d.x()) < 1e-4 and abs(d.z()) < 1e-4
    d = _walk(tool, vp, {Qt.Key_S})
    assert d.y() < -0.5 and abs(d.x()) < 1e-4


def test_a_and_d_step_sideways_without_turning(win):
    vp = win.viewport
    tool = _tool(win)
    heading = vp.camera.forward()
    d = _walk(tool, vp, {Qt.Key_D})
    assert d.x() > 0.5 and abs(d.y()) < 1e-4          # facing +Y, right is +X
    d = _walk(tool, vp, {Qt.Key_A})
    assert d.x() < -0.5 and abs(d.y()) < 1e-4
    assert (vp.camera.forward() - heading).length() < 1e-6


def test_diagonal_is_no_faster_than_straight(win):
    vp = win.viewport
    tool = _tool(win)
    straight = _walk(tool, vp, {Qt.Key_W}, 0.3).length()
    vp.camera.look_from(QVector3D(3, 3, 1.68), QVector3D(0, 1, 0))
    diagonal = _walk(tool, vp, {Qt.Key_W, Qt.Key_D}, 0.3)
    assert abs(diagonal.length() - straight) < 1e-4
    assert diagonal.x() > 0 and diagonal.y() > 0


def test_shift_runs(win):
    vp = win.viewport
    tool = _tool(win)
    walk = _walk(tool, vp, {Qt.Key_W}, 0.3).length()
    vp.camera.look_from(QVector3D(3, 3, 1.68), QVector3D(0, 1, 0))
    run = _walk(tool, vp, {Qt.Key_W}, 0.3, Qt.ShiftModifier).length()
    assert run == pytest.approx(walk * FirstPersonTool.RUN_FACTOR, rel=1e-3)


def test_e_goes_up_and_q_down(win):
    vp = win.viewport
    tool = _tool(win)
    d = _walk(tool, vp, {Qt.Key_E})
    assert d.z() > 0.3 and abs(d.x()) < 1e-4 and abs(d.y()) < 1e-4
    d = _walk(tool, vp, {Qt.Key_Q}, 0.2)
    assert d.z() < -0.1


def test_walls_stop_you_and_alt_goes_through(win):
    vp = win.viewport
    tool = _tool(win)
    _walk(tool, vp, {Qt.Key_W}, 10.0)                   # 15 m at 1.5 m/s
    y = vp.camera.eye().y()
    assert 5.0 < y < 6.0                                # stopped at the north wall
    _walk(tool, vp, {Qt.Key_W}, 2.0, Qt.AltModifier)
    assert vp.camera.eye().y() > 6.0


def test_walking_keeps_the_eye_height_over_the_floor(win):
    vp = win.viewport
    tool = _tool(win)
    _walk(tool, vp, {Qt.Key_E}, 0.5)                    # fly up…
    assert vp.camera.eye().z() > 2.0
    _walk(tool, vp, {Qt.Key_W}, 0.1)                    # …and walking lands you
    assert vp.camera.eye().z() == pytest.approx(1.68, abs=1e-4)


# ---- Keys through the viewport ----------------------------------------------------

def _fired(win, key, press_only=False):
    """Names of the QActions a keystroke on the viewport fires."""
    names = []
    for action in win.findChildren(QAction):
        action.triggered.connect(
            lambda _c=False, n=action.text(): names.append(n))
    if press_only:
        QTest.keyPress(win.viewport, key)
    else:
        QTest.keyClick(win.viewport, key)
    _app.processEvents()
    return names


def _warm_up(win):
    """The first keystroke a freshly shown offscreen window gets is dropped
    before the shortcut map sees it (tests/test_shortcuts.py)."""
    QTest.keyClick(win.viewport, Qt.Key_F1)
    _app.processEvents()


def test_wasd_move_you_instead_of_switching_tools(win):
    tool = _tool(win)
    _warm_up(win)
    for key in (Qt.Key_W, Qt.Key_A, Qt.Key_S, Qt.Key_D, Qt.Key_Q, Qt.Key_E):
        assert _fired(win, key, press_only=True) == []
        assert key in tool.held
        QTest.keyRelease(win.viewport, key)
        assert key not in tool.held
    assert win.viewport.active_tool is tool
    assert not tool.moving


def test_holding_a_key_runs_the_timer(win):
    tool = _tool(win)
    _warm_up(win)
    QTest.keyPress(win.viewport, Qt.Key_W)
    assert tool.moving and tool._timer.isActive()
    QTest.keyRelease(win.viewport, Qt.Key_W)
    assert not tool._timer.isActive()


def test_the_letters_still_switch_tools_from_walk(win):
    win._activate_tool("walk")
    assert isinstance(win.viewport.active_tool, WalkTool)
    _warm_up(win)
    assert "Follow Me" in _fired(win, Qt.Key_W)


def test_ctrl_shortcuts_still_work_in_first_person(win):
    """Ctrl+letter is the window's (Ctrl+S saves, Ctrl+Q quits): only the
    bare letters are claimed. Ctrl+A — Select All — stands in for them here
    because it opens no dialog."""
    tool = _tool(win)
    _warm_up(win)
    names = []
    for action in win.findChildren(QAction):
        action.triggered.connect(
            lambda _c=False, n=action.text(): names.append(n))
    QTest.keyClick(win.viewport, Qt.Key_A, Qt.ControlModifier)
    _app.processEvents()
    assert Qt.Key_A not in tool.held
    assert "Select All" in names


def test_losing_focus_stops_you(win):
    tool = _tool(win)
    _warm_up(win)
    QTest.keyPress(win.viewport, Qt.Key_W)
    assert tool.moving
    tool.on_focus_out(win.viewport)
    assert not tool.moving and not tool._timer.isActive()


def test_leaving_the_tool_stops_you(win):
    tool = _tool(win)
    _warm_up(win)
    QTest.keyPress(win.viewport, Qt.Key_W)
    win._activate_tool("select")
    assert not tool.moving and not tool._timer.isActive()


# ---- Looking ----------------------------------------------------------------------

@pytest.mark.parametrize("button", [Qt.RightButton, Qt.LeftButton])
def test_a_drag_turns_the_head_and_keeps_the_eye(win, button):
    vp = win.viewport
    _tool(win)
    eye = vp.camera.eye()
    c = QPoint(600, 400)
    QTest.mousePress(vp, button, Qt.NoModifier, c)
    QTest.mouseMove(vp, QPoint(700, 400))                # drag right…
    f = vp.camera.forward()
    assert f.x() > 0.1                                   # …looks right (east)
    QTest.mouseMove(vp, QPoint(700, 300))                # drag up…
    assert vp.camera.forward().z() > f.z() + 0.1        # …looks up
    QTest.mouseRelease(vp, button, Qt.NoModifier, QPoint(700, 300))
    assert (vp.camera.eye() - eye).length() < 1e-4
    assert vp._look_drag is None


def test_look_is_a_fixed_rate_per_pixel(win):
    vp = win.viewport
    tool = _tool(win)
    tool.on_look(vp, 100, 0)
    f = vp.camera.forward()
    import math
    turned = math.degrees(math.atan2(f.x(), f.y()))
    assert turned == pytest.approx(100 * FirstPersonTool.LOOK_DEG_PER_PX,
                                   abs=1e-3)


def test_right_click_opens_no_menu(win):
    tool = _tool(win)
    assert tool.context_menu(win.viewport, QPoint(0, 0)) is True


# ---- Where it lives ------------------------------------------------------------------

def test_first_person_sits_beside_walk_in_the_toolbar_and_camera_menu(win):
    keys = [a.text() for a in win.toolbars["walkthrough"].actions()]
    assert keys == ["Position Camera", "Walk", "Look Around", "First Person"]
    assert win._tool_actions["first_person"].shortcut().isEmpty()
