"""Lists inside a tray grow to their rows instead of scrolling on their
own — the tray's scroll is the only one (Marco, 2026-09-14: «no me gusta
hacer scroll dentro del scroll»)."""
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication

_app = QApplication.instance() or QApplication([])


def test_layers_and_scenes_lists_grow_with_their_rows():
    from views.main_window import MainWindow
    from core.layers import Layer
    win = MainWindow()
    try:
        tray = win.tray
        for v in (tray.layers.tree, tray.scenes.list, tray.components._in_model):
            assert v.verticalScrollBarPolicy() == Qt.ScrollBarAlwaysOff
        h0 = tray.layers.tree.height()
        scene = win.viewport.scene
        for i in range(8):
            scene.layers.append(Layer(name=f"capa {i}"))
        tray.layers.refresh()
        assert tray.layers.tree.height() > h0
        assert tray.layers.tree.height() >= 9 * tray.layers.tree.sizeHintForRow(0)
        h_empty = tray.scenes.list.height()
        assert h_empty >= 3 * (tray.scenes.list.fontMetrics().height())  # min rows
    finally:
        win._saved_version = win.viewport.scene.version
        win.close()
