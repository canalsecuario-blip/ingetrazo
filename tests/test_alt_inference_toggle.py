# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""Alt cycles the linear inferences — but Alt+Tab must not (issue #26).

@pacaeiro, on 0.4.2: «I finally discovered that ALT key switch off some
inferences (witch is very good), but the problem is the ALT key itself. In
my daily job (windows 10 and 11) I use a lot the shortcuts ALT and ALT+TAB
to switch between programs, and every time I do that with ingetrazo I lost
the inferences.»

He likes the feature; the key is what betrays it. The cycle used to fire on
the Alt **press**, so every window switch left the mode stuck. Now it fires
on the **release of a clean Alt tap**: no other key in between, and the
window never lost focus — which is exactly what an Alt+Tab is.

The real remedy is the configurable-shortcut editor (Fase 6 of the release
plan); this makes the collision harmless today without moving the key he
already likes.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QFocusEvent, QKeyEvent
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
    vp.keyReleaseEvent(QKeyEvent(QKeyEvent.KeyRelease, key, Qt.NoModifier,
                                 text))


def _close(win, vp):
    win._saved_version = vp.scene.version       # close without the prompt
    win.close()


def test_a_clean_alt_tap_still_cycles():
    """The feature he likes, untouched."""
    win, vp = _viewport()
    try:
        assert vp.linear_inference_mode == "all"
        _press(vp, Qt.Key_Alt)
        _release(vp, Qt.Key_Alt)
        assert vp.linear_inference_mode == "off"
        _press(vp, Qt.Key_Alt)
        _release(vp, Qt.Key_Alt)
        assert vp.linear_inference_mode == "parallel_perp"
        _press(vp, Qt.Key_Alt)
        _release(vp, Qt.Key_Alt)
        assert vp.linear_inference_mode == "all"        # round trip
    finally:
        _close(win, vp)


def test_the_press_alone_does_not_cycle_yet():
    """Holding Alt down must not change anything: the mode is a TAP."""
    win, vp = _viewport()
    try:
        _press(vp, Qt.Key_Alt)
        assert vp.linear_inference_mode == "all"
    finally:
        _close(win, vp)


def test_alt_tab_leaves_the_inferences_alone():
    """The report, reproduced: Alt goes down, the window loses focus to the
    switcher, and whatever release arrives later must not cycle."""
    win, vp = _viewport()
    try:
        _press(vp, Qt.Key_Alt)
        vp.focusOutEvent(QFocusEvent(QFocusEvent.FocusOut,
                                     Qt.ActiveWindowFocusReason))
        _release(vp, Qt.Key_Alt)
        assert vp.linear_inference_mode == "all"
    finally:
        _close(win, vp)


def test_alt_with_another_key_does_not_cycle():
    """Alt+F for a menu, Alt+anything: not a tap, not a cycle."""
    win, vp = _viewport()
    try:
        _press(vp, Qt.Key_Alt)
        _press(vp, Qt.Key_F, "f")
        _release(vp, Qt.Key_F, "f")
        _release(vp, Qt.Key_Alt)
        assert vp.linear_inference_mode == "all"
    finally:
        _close(win, vp)


def test_an_alt_release_out_of_nowhere_does_not_cycle():
    """A release with no press of ours before it — the tail of a shortcut
    handled elsewhere — must not move the mode."""
    win, vp = _viewport()
    try:
        _release(vp, Qt.Key_Alt)
        assert vp.linear_inference_mode == "all"
    finally:
        _close(win, vp)
