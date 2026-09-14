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
    """A throwaway INI for every QSettings() the windows open — the name
    imported into views.main_window included, or the MainWindow reads
    (and, on close, WRITES) the layout of whatever test ran before."""
    path = tmp_path / "prefs.ini"
    factory = lambda *a: QSettings(str(path), QSettings.IniFormat)  # noqa: E731
    import PySide6.QtCore as qc
    import views.main_window as mw
    monkeypatch.setattr(qc, "QSettings", factory)
    monkeypatch.setattr(mw, "QSettings", factory)
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


def test_clean_screen_shows_an_exit_button_at_the_top_right(settings_file):
    """Ctrl+0 hides everything; a floating «Exit clean screen» button at
    the viewport's top-right brings the workspace back for whoever does
    not know the key (Marco, 2026-09-14)."""
    from views.main_window import MainWindow
    win = MainWindow()
    try:
        win.show()
        win._act_clean_screen.setChecked(True)
        btn = win._clean_exit_btn
        assert btn.isVisible() and not win.menuBar().isVisible()
        assert btn.x() + btn.width() <= win.viewport.width() and btn.y() == 12
        btn.click()
        assert not win._act_clean_screen.isChecked()
        assert not btn.isVisible() and win.menuBar().isVisible()
    finally:
        win._saved_version = win.viewport.scene.version
        win.close()


def test_the_sidebar_folds_and_unfolds_from_the_strip_and_ctrl_f5(settings_file):
    """LibreOffice-style sidebar (Marco, 2026-09-14): Window ▸ Sidebar
    (Ctrl+F5) folds the three trays away and brings back the ones that were
    open; the strip at the right edge stays, its tabs show the sidebar with
    that tray on top, and the tab already on top folds it away."""
    from views.main_window import MainWindow
    win = MainWindow()
    try:
        win.show()
        docks = win._sidebar_docks()
        assert win._sidebar_strip.isVisible()
        assert win._act_sidebar.isChecked() and win.tray.isVisible()
        win._act_sidebar.setChecked(False)                     # fold
        assert not any(d.isVisible() for d in docks)
        assert win._sidebar_strip.isVisible()                  # the strip stays
        win._act_sidebar.setChecked(True)                      # unfold
        assert win.tray.isVisible()
        # a tab brings the sidebar back with that tray on top
        win._act_sidebar.setChecked(False)
        win._sidebar_tab_clicked(win.georef_tray)
        assert win._act_sidebar.isChecked() and win.georef_tray.isVisible()
        assert not win.georef_tray.visibleRegion().isEmpty()
        # the tab already on top folds it away again
        win._sidebar_tab_clicked(win.georef_tray)
        assert not win._act_sidebar.isChecked()
        assert not win.georef_tray.isVisible()
    finally:
        win._saved_version = win.viewport.scene.version
        win.close()
