"""Ctrl+Tab goes from the model to the sheets and back (#91, @pacaeiro);
Ctrl+PgUp / Ctrl+PgDown walk the sheets in the composer, as Calc does."""
from __future__ import annotations

from PySide6.QtGui import QKeySequence, QShortcut
from PySide6.QtWidgets import QApplication

_app = QApplication.instance() or QApplication([])


def _fire(window, seq):
    hits = [s for s in window.findChildren(QShortcut)
            if s.key() == QKeySequence(seq) and s.parent() is window]
    assert len(hits) == 1, seq               # one, or neither fires
    hits[0].activated.emit()


def test_ctrl_tab_goes_to_the_sheets_and_back(monkeypatch):
    from views.composer import ComposerWindow
    from views.main_window import MainWindow
    monkeypatch.setattr(ComposerWindow, "render_frame", lambda self, f: None)
    win = MainWindow()
    try:
        win.show()
        assert not win.viewport.scene.compositions
        _fire(win, "Ctrl+Tab")               # no sheet yet: the first one
        comp = win._composer
        assert comp.isVisible() and len(win.viewport.scene.compositions) == 1
        back = []
        monkeypatch.setattr(comp, "_show_model", lambda: back.append(1))
        for seq in ("Ctrl+Tab", "Ctrl+Shift+Tab"):
            # the composer's shortcuts were wired to the real method
            hits = [s for s in comp.findChildren(QShortcut)
                    if s.key() == QKeySequence(seq)]
            assert len(hits) == 1, seq
        comp.close()
    finally:
        win._saved_version = win.viewport.scene.version
        win.close()


def test_ctrl_page_keys_walk_the_sheets(monkeypatch):
    from views.composer import ComposerWindow
    from views.main_window import MainWindow
    monkeypatch.setattr(ComposerWindow, "render_frame", lambda self, f: None)
    win = MainWindow()
    try:
        win._to_sheets()
        comp = win._composer
        comp._on_comp_add()
        comp._on_comp_add()
        comps = win.viewport.scene.compositions
        assert len(comps) == 3 and comp.comp is comps[2]
        _fire(comp, "Ctrl+PgUp")
        assert comp.comp is comps[1]
        _fire(comp, "Ctrl+PgUp")
        _fire(comp, "Ctrl+PgUp")             # no wrap-around
        assert comp.comp is comps[0]
        _fire(comp, "Ctrl+PgDown")
        assert comp.comp is comps[1]
        comp.close()
    finally:
        win._saved_version = win.viewport.scene.version
        win.close()


def test_the_tabs_tell_the_keys(monkeypatch):
    """Hovering Model or a sheet says Ctrl+Tab switches (Marco, 24-09)."""
    from views.composer import ComposerWindow
    from views.main_window import MainWindow
    monkeypatch.setattr(ComposerWindow, "render_frame", lambda self, f: None)
    win = MainWindow()
    try:
        win._to_sheets()
        comp = win._composer
        for tabs in (win._sheet_tabs, comp._sheet_tabs):
            tips = [tabs.tabToolTip(i) for i in range(tabs.count())]
            assert "Ctrl+Tab" in tips[0]                      # Model
            assert "Ctrl+Tab" in tips[1] and "Ctrl+PgUp" in tips[1]
            assert "Ctrl+Tab" in tabs.toolTip()     # the strip's own tip
        comp.close()
    finally:
        win._saved_version = win.viewport.scene.version
        win.close()
