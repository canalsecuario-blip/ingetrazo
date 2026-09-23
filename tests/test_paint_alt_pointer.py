# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""@pacaeiro, #47 point 1: «Activate Paint tool. Press Alt and release it.
Icon changed but we're still on Paint mode.» The first Alt release hands
the keyboard to the menu bar, so the viewport never heard the next press:
every other tap the pointer stayed a bucket. Alt is now heard at
application level, wherever the key event lands."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, Qt  # noqa: E402
from PySide6.QtGui import QKeyEvent  # noqa: E402
from PySide6.QtWidgets import QApplication, QMenuBar  # noqa: E402

if QApplication.instance() is None:
    QApplication([])

from views.viewport import Viewport  # noqa: E402


def _paint_viewport():
    from tools.paint import PaintTool
    vp = Viewport(None)
    vp.flash_status = lambda *a, **k: None
    tool = PaintTool()
    tool.icon = "paint"                  # as MainWindow tags its tools
    vp.active_tool = tool
    return vp


def _key(target, press: bool):
    t = QEvent.KeyPress if press else QEvent.KeyRelease
    mods = Qt.AltModifier if press else Qt.NoModifier
    QApplication.sendEvent(target, QKeyEvent(t, Qt.Key_Alt, mods))


def test_alt_taps_on_the_menu_bar_still_reach_the_viewport():
    """The pointer follows the key even while the menu bar holds focus."""
    vp = _paint_viewport()
    shown = []
    vp._apply_tool_cursor = lambda: shown.append(vp._alt_down)
    bar = QMenuBar()                    # where the focus goes after a tap
    _key(bar, True)
    assert vp._alt_down is True
    _key(bar, False)
    assert vp._alt_down is False


def test_a_tap_toggles_the_eyedropper_and_it_stays():
    """SketchUp since 2021.1 (Marco: «se alterna con Alt, no es que se
    mantenga presionado»): tap = eyedropper on, it stays after the release;
    tap again = off."""
    from tools.paint import PaintTool
    PaintTool.sample_armed = False
    vp = _paint_viewport()
    bar = QMenuBar()
    try:
        _key(bar, True)
        _key(bar, False)
        assert PaintTool.sample_armed is True      # stays after the release
        _key(bar, True)
        _key(bar, False)
        assert PaintTool.sample_armed is False     # tapped again: off
    finally:
        PaintTool.sample_armed = False


def test_alt_tab_is_not_a_tap():
    """Alt+Tab all day (@pacaeiro, #26) must not arm the eyedropper."""
    from tools.paint import PaintTool
    PaintTool.sample_armed = False
    vp = _paint_viewport()
    bar = QMenuBar()
    try:
        _key(bar, True)
        QApplication.sendEvent(bar, QKeyEvent(QEvent.KeyPress, Qt.Key_Tab,
                                              Qt.AltModifier))
        _key(bar, False)
        assert PaintTool.sample_armed is False
    finally:
        PaintTool.sample_armed = False
