# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""Alt cycles the linear inferences DURING an operation, as SketchUp does.

@pacaeiro, on 0.4.2 (issue #26): «I finally discovered that ALT key switch
off some inferences (witch is very good), but the problem is the ALT key
itself. In my daily job I use a lot the shortcuts ALT and ALT+TAB to switch
between programs, and every time I do that with ingeTrazo I lost the
inferences.»

The key is right — Marco's own SketchUp screenshot reads «Alt =
Activar/desactivar "Inferencias lineales" (Ninguno activo)», the same three
states we cycle. What was wrong is WHEN: SketchUp offers it only after the
first click of a line, and we had it global, at any idle moment. So an
Alt+Tab with nothing in progress moved a mode he was not even using.

Gated on an operation being under way, his daily window switching cannot
touch it: idle, there is nothing to steal.

The first attempt cycled on the RELEASE of a clean tap instead, and he
tested it from main: «sometimes it triggers the command, some other do
not». Measured on Marco's desktop with an application-level probe — the
Alt release is what makes Qt's menu bar take focus, so it lands on the
QMenuBar and the focus ping-pongs. One tap in six reached the viewport.
Hence: act on the PRESS, and swallow the release so the menu bar never
takes it.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QFocusEvent, QKeyEvent, QVector3D
from PySide6.QtWidgets import QApplication

_app = QApplication.instance() or QApplication([])


def _viewport():
    from views.main_window import MainWindow
    win = MainWindow()
    win.show()
    _app.processEvents()
    return win, win.viewport


def _press(vp, key, text=""):
    vp.keyPressEvent(QKeyEvent(QKeyEvent.KeyPress, key, Qt.NoModifier, text))


def _release(vp, key, text=""):
    ev = QKeyEvent(QKeyEvent.KeyRelease, key, Qt.NoModifier, text)
    vp.keyReleaseEvent(ev)
    return ev


def _busy(vp):
    """Put the active tool mid-operation, the way the first click does."""
    vp.active_tool.start_point = QVector3D(0.0, 0.0, 0.0)
    assert vp._tool_busy(vp.active_tool)


def _close(win, vp):
    win._saved_version = vp.scene.version
    win.close()


def test_alt_does_nothing_when_no_operation_is_under_way():
    """The whole of issue #26: his Alt+Tab happens between operations."""
    win, vp = _viewport()
    try:
        assert vp.linear_inference_mode == "all"
        _press(vp, Qt.Key_Alt)
        _release(vp, Qt.Key_Alt)
        assert vp.linear_inference_mode == "all"
    finally:
        _close(win, vp)


def test_alt_cycles_while_a_line_is_being_drawn():
    win, vp = _viewport()
    try:
        win._activate_tool("line")
        _busy(vp)
        for expected in ("off", "parallel_perp", "all"):
            _press(vp, Qt.Key_Alt)
            _release(vp, Qt.Key_Alt)
            assert vp.linear_inference_mode == expected
    finally:
        _close(win, vp)


def test_it_acts_on_the_press_so_the_menu_bar_cannot_steal_it():
    """Qt's menu bar takes focus on the Alt RELEASE. Acting on the press is
    what makes the toggle reach us at all."""
    win, vp = _viewport()
    try:
        win._activate_tool("line")
        _busy(vp)
        _press(vp, Qt.Key_Alt)
        assert vp.linear_inference_mode == "off"      # already done
    finally:
        _close(win, vp)


def test_the_release_is_swallowed_so_the_menu_bar_never_sees_it():
    win, vp = _viewport()
    try:
        win._activate_tool("line")
        _busy(vp)
        _press(vp, Qt.Key_Alt)
        ev = _release(vp, Qt.Key_Alt)
        assert ev.isAccepted()
    finally:
        _close(win, vp)


def test_an_idle_alt_release_is_left_alone_for_the_menus():
    """With nothing in progress the key is not ours: Alt must keep opening
    the menu bar like it does in every other program."""
    win, vp = _viewport()
    try:
        _press(vp, Qt.Key_Alt)
        assert vp._alt_tap is False
    finally:
        _close(win, vp)


def test_losing_focus_drops_the_claim_on_the_release():
    win, vp = _viewport()
    try:
        win._activate_tool("line")
        _busy(vp)
        _press(vp, Qt.Key_Alt)
        vp.focusOutEvent(QFocusEvent(QFocusEvent.FocusOut,
                                     Qt.ActiveWindowFocusReason))
        assert vp._alt_tap is False
    finally:
        _close(win, vp)


def test_the_toggle_lasts_one_operation_and_no_longer():
    """SketchUp's rule, checked by Marco against the real thing: «desactivo
    con alt, termino de dibujar la línea, aprieto la flechita y aprieto otra
    vez la línea y está activo la inferencia». Ours was sticky — off stayed
    off for the session, which is a trap, and it is what made an accidental
    Alt+Tab bite so hard in issue #26."""
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QMouseEvent

    win, vp = _viewport()
    try:
        win._activate_tool("line")
        _busy(vp)
        _press(vp, Qt.Key_Alt)
        assert vp.linear_inference_mode == "off"

        vp.active_tool.start_point = None          # the line was finished
        # the NEXT gesture starts clean
        vp.mousePressEvent(QMouseEvent(
            QMouseEvent.MouseButtonPress, QPointF(5, 5), Qt.LeftButton,
            Qt.LeftButton, Qt.NoModifier))
        assert vp.linear_inference_mode == "all"
    finally:
        _close(win, vp)


def test_a_click_mid_operation_does_not_give_the_inferences_back():
    """The second click of a line is not a new gesture."""
    from PySide6.QtCore import QPointF
    from PySide6.QtGui import QMouseEvent

    win, vp = _viewport()
    try:
        win._activate_tool("line")
        _busy(vp)
        _press(vp, Qt.Key_Alt)
        vp.mousePressEvent(QMouseEvent(
            QMouseEvent.MouseButtonPress, QPointF(5, 5), Qt.LeftButton,
            Qt.LeftButton, Qt.NoModifier))
        assert vp.linear_inference_mode == "off"
    finally:
        _close(win, vp)


def test_changing_tool_gives_the_inferences_back():
    win, vp = _viewport()
    try:
        win._activate_tool("line")
        _busy(vp)
        _press(vp, Qt.Key_Alt)
        assert vp.linear_inference_mode == "off"
        win._activate_tool("select")
        assert vp.linear_inference_mode == "all"
    finally:
        _close(win, vp)


def test_escape_gives_the_inferences_back():
    win, vp = _viewport()
    try:
        win._activate_tool("line")
        _busy(vp)
        _press(vp, Qt.Key_Alt)
        vp.escape()
        assert vp.linear_inference_mode == "all"
    finally:
        _close(win, vp)


def test_the_status_bar_offers_alt_and_names_the_state():
    """SketchUp puts the offer AND the current state on the same line while
    drawing: «Alt = Activar/desactivar "Inferencias lineales" (Ninguno
    activo)»."""
    from views.status_hints import alt_inference_hint, hint_for

    assert "all on" in alt_inference_hint("all")
    assert "none active" in alt_inference_hint("off")
    assert "parallel" in alt_inference_hint("parallel_perp")

    win, vp = _viewport()
    try:
        win._activate_tool("line")
        key = win._tool_key(vp.active_tool)
        idle = hint_for(key, vp.active_tool, None, "all")
        _busy(vp)
        drawing = hint_for(key, vp.active_tool, None, "off")
        assert "Alt" not in idle, "nothing to offer before the first click"
        assert "Alt" in drawing and "none active" in drawing
    finally:
        _close(win, vp)
