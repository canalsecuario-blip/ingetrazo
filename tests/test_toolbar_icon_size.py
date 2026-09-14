# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""One toolbar icon size for the model window AND the sheet composer
(Marco, 2026-09-14: «no sé si habrás considerado también los iconos de
composiciones»)."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication, QToolBar

_app = QApplication.instance() or QApplication([])


@pytest.fixture
def settings_file(tmp_path, monkeypatch):
    path = tmp_path / "prefs.ini"
    import PySide6.QtCore as qc
    monkeypatch.setattr(qc, "QSettings",
                        lambda *a: QSettings(str(path), QSettings.IniFormat))
    return path


def test_the_size_reaches_the_composer_toolbars_live_and_on_build(settings_file, monkeypatch):
    from views.composer import ComposerWindow
    from views.main_window import MainWindow
    monkeypatch.setattr(ComposerWindow, "render_frame", lambda self, f: None)
    win = MainWindow()
    try:
        win.set_toolbar_icon_size(40)
        comp = ComposerWindow(win)
        win._composer = comp
        try:
            bars = win.findChildren(QToolBar) + comp.findChildren(QToolBar)
            assert bars and all(tb.iconSize().width() == 40 for tb in bars)
            win.set_toolbar_icon_size(20)                  # live, both windows
            assert all(tb.iconSize().width() == 20 for tb in bars)
        finally:
            comp.close()
    finally:
        win._saved_version = win.viewport.scene.version
        win.close()
