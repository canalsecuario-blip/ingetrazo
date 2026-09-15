# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""The status bar shows ONE hint for the tool and its step (Marco,
2026-09-15: a strip of every shortcut at once «no es bueno»)."""
from __future__ import annotations

from PySide6.QtGui import QVector3D

from tools.arc import ArcTool
from tools.fillet import FilletTool
from tools.line import LineTool
from views.status_hints import HINTS, NAV_HINTS, hint_for, phase_of


def test_the_hint_follows_the_tools_step():
    line = LineTool()
    idle = hint_for("line", line)
    assert idle.startswith("Click the start point")
    line.start_point = QVector3D(0, 0, 0)
    assert hint_for("line", line).startswith("Click the end point")
    arc = ArcTool()
    assert phase_of("arc", arc) == "idle"
    arc.start_point = QVector3D(0, 0, 0)
    assert phase_of("arc", arc) == "end"
    arc.end_point = QVector3D(1, 0, 0)
    assert phase_of("arc", arc) == "bulge"
    assert "Ns" in hint_for("arc", arc)
    fil = FilletTool()
    assert "radius" in hint_for("fillet", fil)
    fil.sizing = True
    assert phase_of("fillet", fil) == "sizing"


def test_navigation_and_unknown_tools_have_a_line_too():
    class Odd:
        name = "Odd"
    assert hint_for(None, Odd()).startswith("Odd")
    assert hint_for("line", LineTool(), nav_mode="orbit") == NAV_HINTS["orbit"]


def test_every_registered_tool_has_a_hint():
    from PySide6.QtWidgets import QApplication
    import pytest
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    elif not isinstance(app, QApplication):
        pytest.skip("another Qt application flavour is already running")
    from views.main_window import MainWindow
    win = MainWindow()
    missing = [k for k in win._tools if k not in HINTS and not k.startswith("plugin_")]
    assert not missing, missing
    win._activate_tool("line")
    assert win._hint_label.text().startswith("Click the start point")
    win._activate_nav("orbit")
    assert win._hint_label.text().startswith("Drag to orbit")
    win.close()
