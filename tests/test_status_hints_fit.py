# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""Every status hint fits the bar, in both languages.

The bar caps its message at half its width (Marco, 2026-09-15: «que no
llegue hasta el otro extremo derecho»), and what does not fit is elided
with an ellipsis — so an overlong line does not wrap, it silently loses its
end. That is where the modifiers live, which is exactly the part you need.

He caught one: «no sale completo el texto». The survey that followed found
it was not one line but SIXTEEN, across eight tools whose hints had grown
over time — and that Spanish is the language that hurts, running a fifth
longer than the English it is translated from (8 elided against 2).

So this measures with the REAL font metrics at the narrowest window worth
caring about, in both languages, for every tool and phase. A hint that
grows past the bar now fails here instead of on a user's screen.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtGui import QFontMetrics, QVector3D
from PySide6.QtWidgets import QApplication

from core.i18n import set_language
from views.status_hints import HINTS, hint_for

_app = QApplication.instance() or QApplication([])

#: The narrowest window we design for — a 1366×768 laptop, which is what
#: sent the toolbar icons back to 24 px in the first place.
_NARROW_PX = 1366


def _overlong(language: str):
    """Every (tool, phase, mode) hint that would be elided, measured."""
    from views.main_window import MainWindow

    set_language(language)
    win = MainWindow()
    win.show()
    win.resize(_NARROW_PX, 900)
    _app.processEvents()
    vp, bar = win.viewport, win.statusBar()
    fm = QFontMetrics(bar._msg.font())
    cap = int(bar.width() * bar.MESSAGE_SHARE) - 4
    bad = []
    try:
        for key in sorted(HINTS):
            try:
                win._activate_tool(key)
            except Exception:       # noqa: BLE001 — not every key is a tool
                continue
            tool = vp.active_tool
            if tool is None:
                continue
            for started in (False, True):
                if started:
                    try:
                        tool.start_point = QVector3D(1.0, 1.0, 0.0)
                    except Exception:   # noqa: BLE001 — read-only on some
                        pass
                for mode in ("all", "off"):
                    text = hint_for(win._tool_key(tool), tool, None, mode)
                    width = fm.horizontalAdvance(text)
                    if width > cap:
                        bad.append(f"{key} ({width}px > {cap}px): {text}")
    finally:
        win._saved_version = vp.scene.version
        win.close()
        set_language("en")
    return bad


@pytest.mark.parametrize("language", ["en", "es"])
def test_no_hint_is_elided_on_a_1366_screen(language):
    bad = _overlong(language)
    assert not bad, "\n".join(bad)
