# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""Tooltips that wrap.

Qt shows a plain-text tooltip on ONE line, however long, and only folds
it when it would not fit the screen; a rich-text one wraps into a box of
a comfortable width. So a long hint read as a strip across the window
while a longer one next to it came out as a neat block (Marco, 2026-09-20:
«en algunos sale en una línea que no me gusta como el texto es extenso,
pero en otras sale en tipo cuadro delimitado que sale bien»).

The filter turns every plain-text tooltip into rich text on its way to
the screen — escaped, so a ``<>`` or an ``&`` in a hint still reads as
written — and leaves tooltips that already are rich text, and widgets
that make theirs up on the spot (no ``toolTip()``), to Qt.
"""
from __future__ import annotations

import html

from PySide6.QtCore import QEvent, QObject
from PySide6.QtGui import Qt
from PySide6.QtWidgets import QToolTip, QWidget


def wrapped(text: str) -> str:
    """*text* as rich text that wraps, or itself when it already is."""
    if not text or Qt.mightBeRichText(text):
        return text
    return "<p style='white-space:normal'>" + \
        html.escape(text).replace("\n", "<br>") + "</p>"


class WrappingToolTips(QObject):
    """Application-wide event filter: ``app.installEventFilter(...)``."""

    def eventFilter(self, obj, event) -> bool:  # noqa: N802 — Qt override
        if event.type() == QEvent.ToolTip and isinstance(obj, QWidget):
            text = obj.toolTip()
            if text and not Qt.mightBeRichText(text):
                QToolTip.showText(event.globalPos(), wrapped(text), obj)
                event.accept()
                return True
        return False
