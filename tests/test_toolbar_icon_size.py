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


def test_the_main_toolbar_starts_with_save(settings_file, monkeypatch):
    """Marco, 2026-09-14: the Save icon on the model's Main bar too, before
    the Select arrow; it triggers the same save as the menu."""
    from views.main_window import MainWindow
    win = MainWindow()
    try:
        acts = [a for a in win.toolbars["main"].actions() if not a.isSeparator()]
        assert acts[0] is win._act_save_tb and acts[0].text() == "Save"
        assert acts[1] is win._tool_actions["select"]
        called = []
        monkeypatch.setattr(win, "_on_save", lambda: called.append(True))
        win._act_save_tb.trigger()
        assert called == [True]
    finally:
        win._saved_version = win.viewport.scene.version
        win.close()


def test_a_fresh_install_gets_marcos_layout_and_large_icons(settings_file, monkeypatch):
    """No saved state → the factory blob (resources/ui/default_layout.state)
    and 32 px icons: Draw and Annotate stand at the left, the rest along
    the top, as Marco arranged them (2026-09-14: «así como está… por
    defecto para cualquier persona que instale el programa»)."""
    from PySide6.QtCore import Qt
    from views.icons import toolbar_icon_px
    from views.main_window import MainWindow
    assert toolbar_icon_px() == 32
    win = MainWindow()
    try:
        assert win.toolBarArea(win.toolbars["draw"]) == Qt.LeftToolBarArea
        assert win.toolBarArea(win.toolbars["annotate"]) == Qt.LeftToolBarArea
        for name in ("main", "modify", "view", "sections", "views"):
            assert win.toolBarArea(win.toolbars[name]) == Qt.TopToolBarArea, name
        assert all(tb.iconSize().width() == 32 for tb in win.toolbars.values())
    finally:
        win._saved_version = win.viewport.scene.version
        win.close()
