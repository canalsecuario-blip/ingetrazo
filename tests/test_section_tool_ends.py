# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""Issue #62 (@pacaeiro): the Section Plane tool ends after one plane, and
the name prompt can be switched off."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPointF, QSettings, Qt  # noqa: E402
from PySide6.QtGui import QVector3D  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

if QApplication.instance() is None:
    QApplication([])

from core.history import History  # noqa: E402
from core.scene import Scene  # noqa: E402
from tools.base import ToolContext  # noqa: E402
from tools.section import SectionPlaneTool  # noqa: E402


class _Win:
    def __init__(self):
        self.activated: list = []
        self.prompted: list = []

    def _activate_tool(self, key):
        self.activated.append(key)

    def prompt_section_name(self, plane):
        self.prompted.append(plane)


class _Vp:
    def __init__(self, scene, win):
        self.scene = scene
        self.history = History(scene)
        self._win = win
        self.camera = None

    def window(self):
        return self._win

    def update(self):
        pass

    def flash_status(self, *a, **k):
        pass


def test_one_plane_then_back_to_select():
    scene = Scene()
    win = _Win()
    vp = _Vp(scene, win)
    tool = SectionPlaneTool()
    tool._normal = QVector3D(0, 0, 1)
    tool.on_click(ToolContext(viewport=vp, world=QVector3D(0, 0, 1),
                              screen=QPointF(0, 0), modifiers=Qt.NoModifier,
                              snap=None))
    assert len(scene.section_planes) == 1
    assert win.prompted and win.activated == ["select"]


def test_the_name_prompt_can_be_switched_off():
    from views.main_window import MainWindow
    from core.section import SectionPlane
    win = MainWindow()
    try:
        QSettings().setValue("section/ask_name", "0")
        plane = SectionPlane(QVector3D(0, 0, 0), QVector3D(0, 0, 1),
                             name="Sección 1", symbol="A")
        win.prompt_section_name(plane)          # returns without a dialog
        assert plane.name == "Sección 1" and plane.symbol == "A"
    finally:
        QSettings().setValue("section/ask_name", "1")
        win._saved_version = win.viewport.scene.version
        win.close()
