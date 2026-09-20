# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""Ctrl+A tells the rest of the program (@pacaeiro, issue #38).

Select All built the selection set by hand, behind ``Scene.select()``'s
back, so the scene version never moved: the status bar counted the
entities, the viewport drew none of them selected, Entity Info said
"nothing selected" — and the first drag with Move brought them all along.
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QVector3D
from PySide6.QtWidgets import QApplication

if QApplication.instance() is None:
    QApplication(sys.argv[:1])


def V(x, y, z=0.0):
    return QVector3D(float(x), float(y), float(z))


def test_select_all_bumps_the_version_and_notifies():
    from views.main_window import MainWindow
    win = MainWindow()
    try:
        scene = win.viewport.scene
        scene.mesh.add_face([V(0, 0), V(2, 0), V(2, 2), V(0, 2)])
        seen: list = []
        win.viewport.sceneVersionChanged.connect(seen.append)

        before = scene.version
        win._on_select_all()

        assert scene.selection, "nothing selected"
        assert scene.version > before          # the GL colour caches are keyed on it
        assert seen and seen[-1] == scene.version   # and the tray hears about it
    finally:
        win._saved_version = win.viewport.scene.version
        win.close()
