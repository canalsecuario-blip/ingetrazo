"""The Python console follows the theme (#92, @xyont: «a Python console
still has black color background» in the light theme) — also the text
already in it when the theme changes with the console open."""
from __future__ import annotations

from PySide6.QtWidgets import QApplication

from views.theme import dark_palette, light_palette

_app = QApplication.instance() or QApplication([])


def test_the_console_takes_the_theme_and_follows_it(monkeypatch):
    from plugins.python_console import _PALETTES, PythonConsoleDialog
    from views.main_window import MainWindow
    before = _app.palette()
    win = MainWindow()
    try:
        _app.setPalette(light_palette())
        dlg = PythonConsoleDialog(win.viewport, win)
        light = _PALETTES["light"]
        assert light["bg"] in dlg._output.styleSheet()
        assert light["title"] in dlg._output.document().toHtml()
        _app.setPalette(dark_palette())
        _app.processEvents()
        dark = _PALETTES["dark"]
        assert dark["bg"] in dlg._output.styleSheet()
        html = dlg._output.document().toHtml()
        assert dark["title"] in html and light["title"] not in html
        dlg.close()
    finally:
        _app.setPalette(before)
        win._saved_version = win.viewport.scene.version
        win.close()
