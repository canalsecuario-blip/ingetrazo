# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""Long tooltips wrap into a box (Marco, 2026-09-20: some hints came out
as one long strip, others as a neat block — Qt only wraps rich text)."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QEvent, QPoint
from PySide6.QtGui import QHelpEvent
from PySide6.QtWidgets import QApplication, QToolTip, QWidget

_app = QApplication.instance() or QApplication([])


def test_plain_text_becomes_rich_text_escaped_and_rich_text_is_left_alone():
    from views.tooltips import wrapped
    assert wrapped("") == ""
    assert wrapped("<b>bold</b>") == "<b>bold</b>"            # already rich
    out = wrapped("Text (<> = measured value) & more\nnext line")
    assert out.startswith("<p style='white-space:normal'>")
    assert "&lt;&gt;" in out and "&amp;" in out and "<br>" in out
    assert "<>" not in out


def test_the_filter_shows_the_wrapped_text_for_a_widgets_tooltip():
    from views.tooltips import WrappingToolTips
    shown = []
    orig = QToolTip.showText
    QToolTip.showText = staticmethod(lambda pos, text, *a: shown.append(text))
    try:
        w = QWidget()
        w.setToolTip("Zoom: drag up to zoom in (Ctrl+wheel does the same)")
        f = WrappingToolTips()
        ev = QHelpEvent(QEvent.ToolTip, QPoint(1, 1), QPoint(10, 10))
        assert f.eventFilter(w, ev) is True
        assert shown and shown[-1].startswith("<p style='white-space:normal'>")
        assert "Ctrl+wheel" in shown[-1]
        rich = QWidget()
        rich.setToolTip("<b>already</b> rich")
        assert f.eventFilter(rich, ev) is False           # Qt's own path
        bare = QWidget()
        assert f.eventFilter(bare, ev) is False           # nothing to show
    finally:
        QToolTip.showText = orig
