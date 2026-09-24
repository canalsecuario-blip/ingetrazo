"""Every composer tool shows its cursor on the sheet, also after the
pointer has crossed an item with a cursor of its own (#79, @pacaeiro:
«If I press any of the tools (zoom, pan, etc...), the cursor is always the
Select, default cursor»)."""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

_app = QApplication.instance() or QApplication([])


def test_each_tool_shows_its_cursor_after_an_item_hover(monkeypatch):
    from views.composer import ComposerWindow
    from views.main_window import MainWindow
    monkeypatch.setattr(ComposerWindow, "render_frame", lambda self, f: None)
    win = MainWindow()
    comp = ComposerWindow(win)
    try:
        vp = comp._view.viewport()
        want = {"pan": Qt.OpenHandCursor, "zoom": Qt.SizeVerCursor,
                "zoom_ventana": Qt.CrossCursor, "texto": Qt.CrossCursor,
                "cota": Qt.CrossCursor, "select": Qt.ArrowCursor}
        for mode, shape in want.items():
            # What QGraphicsView leaves on the viewport after the pointer
            # leaves an item with a cursor of its own.
            vp.setCursor(Qt.SizeAllCursor)
            comp._tool_actions[mode].trigger()
            assert vp.cursor().shape() == shape, mode
    finally:
        comp.close()
        win._saved_version = win.viewport.scene.version
        win.close()
