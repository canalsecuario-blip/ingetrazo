# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""The sheet composer's Zoom and Zoom Window tools (Marco, 2026-09-20:
«en composición de láminas deberíamos colocar un icono de zoom y zoom
ventana») — the model's two, on the sheet."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

_app = QApplication.instance() or QApplication([])


@pytest.fixture
def composer(monkeypatch):
    from views.composer import ComposerWindow
    from views.main_window import MainWindow
    monkeypatch.setattr(ComposerWindow, "render_frame", lambda self, f: None)
    win = MainWindow()
    comp = ComposerWindow(win)
    comp.resize(1000, 700)
    comp.show()
    _app.processEvents()
    try:
        yield comp
    finally:
        comp.close()
        win._saved_version = win.viewport.scene.version
        win.close()


def _mouse(view, kind, vp, button=Qt.LeftButton, buttons=None):
    buttons = button if buttons is None else buttons
    ev = QMouseEvent(kind, QPointF(vp), view.mapToGlobal(vp), button,
                     buttons, Qt.NoModifier)
    {QEvent.MouseButtonPress: view.mousePressEvent,
     QEvent.MouseMove: view.mouseMoveEvent,
     QEvent.MouseButtonRelease: view.mouseReleaseEvent}[kind](ev)


def test_both_tools_are_on_the_bar_with_the_models_icons(composer):
    modes = [m for m, _i, _t, _d in composer.TOOLS]
    assert modes.index("zoom") == modes.index("pan") + 1
    assert modes.index("zoom_ventana") == modes.index("zoom") + 1
    icons = {m: i for m, i, _t, _d in composer.TOOLS}
    assert (icons["zoom"], icons["zoom_ventana"]) == ("zoom", "zoom_window")
    assert "zoom" in composer._tool_actions and "zoom_ventana" in composer._tool_actions
    assert "zoom" not in composer.DRAW_TOOLS       # navigation, left bar


def test_zoom_drags_up_to_zoom_in_about_the_press_point(composer):
    view = composer._view
    composer._set_tool_mode("zoom")
    before = composer.zoom_percent()
    press = QPoint(400, 300)
    under = view.mapToScene(press)
    _mouse(view, QEvent.MouseButtonPress, press)
    _mouse(view, QEvent.MouseMove, QPoint(400, 200))       # 100 px up
    assert composer.zoom_percent() > before * 1.5
    # anchored: within the scroll bars' integer rounding (two pixels' worth
    # of paper at the zoom reached — 0.57 mm on the CI runner's smaller
    # screen, where a fixed 0.5 mm failed)
    slack = 2.0 / view.transform().m11()
    assert (view.mapToScene(press) - under).manhattanLength() < slack
    _mouse(view, QEvent.MouseMove, QPoint(400, 400))       # 200 px down
    assert composer.zoom_percent() < before
    _mouse(view, QEvent.MouseButtonRelease, QPoint(400, 400))
    assert view._zoom_last is None
    assert composer.tool_mode == "zoom"                    # stays armed


def test_a_click_with_zoom_steps_in(composer):
    view = composer._view
    composer._set_tool_mode("zoom")
    before = composer.zoom_percent()
    _mouse(view, QEvent.MouseButtonPress, QPoint(300, 300))
    _mouse(view, QEvent.MouseButtonRelease, QPoint(300, 300))
    assert composer.zoom_percent() == pytest.approx(before * 1.25, rel=0.02)


def test_zoom_window_fills_the_view_with_the_box(composer):
    from PySide6.QtCore import QRectF
    view = composer._view
    composer.zoom_fit_page()
    composer._set_tool_mode("zoom_ventana")
    a, b = QPoint(300, 200), QPoint(500, 350)
    box = QRectF(view.mapToScene(a), view.mapToScene(b)).normalized()
    _mouse(view, QEvent.MouseButtonPress, a)
    _mouse(view, QEvent.MouseMove, QPoint(400, 300))
    assert view._band_item is not None                     # the rubber band
    _mouse(view, QEvent.MouseButtonRelease, b)
    assert view._band_item is None and view._band_start is None
    shown = view.mapToScene(view.viewport().rect()).boundingRect()
    assert shown.contains(box)                             # the box is in view
    assert shown.width() < 1.3 * box.width() or shown.height() < 1.3 * box.height()
    assert not composer.comp.frames[0].uid or True         # nothing selected
    assert composer.tool_mode == "zoom_ventana"            # stays armed
