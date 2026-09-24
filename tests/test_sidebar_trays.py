"""The right-side trays (Properties, BIM, Terrain) always have a way back:
their Window-menu entries work, and folding the sidebar brings back every
tray that was open — not just the tab in front (Marco, 0.5.1 Flatpak: «no
veo las pestañas de terreno y BIM», the menu entries greyed out)."""
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




def test_the_window_menu_can_bring_back_every_tray(settings_file):
    from views.main_window import MainWindow
    win = MainWindow()
    for dock in win._sidebar_docks():
        assert dock.toggleViewAction().isEnabled(), dock.objectName()
    win.bim_tray.hide()
    assert not win.bim_tray.toggleViewAction().isChecked()
    win.bim_tray.toggleViewAction().trigger()
    assert not win.bim_tray.isHidden()


def test_unfolding_the_sidebar_brings_back_the_tabs_behind(settings_file,
                                                         monkeypatch):
    from PySide6.QtWidgets import QDockWidget
    from views.main_window import MainWindow
    win = MainWindow()
    win.resize(1400, 900)
    win.show()
    for _ in range(5):
        _app.processEvents()
    # On a real screen a tray tabbed behind another is not visible; the
    # offscreen platform shows them all, so play the real screen here.
    front = win.tray
    real = QDockWidget.isVisible
    monkeypatch.setattr(QDockWidget, "isVisible",
                        lambda d: real(d) and d is front)
    win._set_sidebar_visible(False)
    win._set_sidebar_visible(True)
    for dock in win._sidebar_docks():
        assert not dock.isHidden(), dock.objectName()


def _shown(win):
    """The Window-menu checks follow the trays once the window is up."""
    win.show()
    for _ in range(5):
        _app.processEvents()
    return win


def _close(win):
    win._saved_version = win.viewport.scene.version
    win.close()


def test_every_tray_opens_at_start_up_unless_the_menu_closed_it(settings_file):
    from views.main_window import MainWindow
    win = _shown(MainWindow())
    win.bim_tray.hide()                 # lost by a fold, not by the menu
    win.georef_tray.toggleViewAction().trigger()    # closed from the menu
    assert win.georef_tray.isHidden()
    _close(win)                         # the layout is saved on close

    win = _shown(MainWindow())
    assert not win.tray.isHidden()
    assert not win.bim_tray.isHidden()
    assert win.georef_tray.isHidden()
    win.georef_tray.toggleViewAction().trigger()    # back from the menu
    _close(win)

    win = _shown(MainWindow())
    assert not any(d.isHidden() for d in win._sidebar_docks())
    _close(win)


def test_a_folded_sidebar_opens_unfolded(settings_file):
    from views.main_window import MainWindow
    win = _shown(MainWindow())
    win._set_sidebar_visible(False)
    _close(win)
    win = _shown(MainWindow())
    assert not any(d.isHidden() for d in win._sidebar_docks())
    _close(win)
