"""A dialog opened from a toolbar-dropdown panel (Styles, Shadows, Dimension
style) hangs on the main window, with the dropdown closed first. Parented to
the menu popup, Wayland never maps it: «Añadir localización se queda
cargando» (Marco, 0.5.1 Flatpak, 24-09)."""
from __future__ import annotations

from PySide6.QtWidgets import (QApplication, QMainWindow, QMenu, QWidget,
                               QWidgetAction)

from views.tray import _dialog_parent

_app = QApplication.instance() or QApplication([])


class _Panel(QWidget):
    def __init__(self, window):
        super().__init__()
        self._window = window


class _Menu(QMenu):
    closed = 0

    def close(self):
        self.closed += 1
        return super().close()


def test_a_panel_in_a_dropdown_closes_it_and_lends_the_main_window():
    win = QMainWindow()
    panel = _Panel(win)
    menu = _Menu(win)            # the offscreen platform keeps no popup open
    wa = QWidgetAction(menu)
    wa.setDefaultWidget(panel)
    menu.addAction(wa)
    assert _dialog_parent(panel) is win
    assert menu.closed == 1


def test_a_loose_panel_still_lends_the_main_window():
    win = QMainWindow()
    assert _dialog_parent(_Panel(win)) is win
