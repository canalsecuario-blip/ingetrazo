# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""After a document loads, the garbage collector is kept out of the way of
drawing: a raised young-generation threshold (Python 3.14's incremental
collector walked slices of the plaza's 1.3 M objects on almost every hover —
Marco, 2026-09-14). gc.freeze was measured and rejected: fewer pauses but
every allocation-heavy path slower."""
import gc
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication

_app = QApplication.instance() or QApplication([])


def test_a_new_document_raises_the_gc_threshold_and_does_not_freeze():
    from views.main_window import MainWindow
    win = MainWindow()
    old = gc.get_threshold()
    try:
        gc.set_threshold(2000, 10, 0)
        win._on_new()
        assert gc.get_threshold()[0] == MainWindow.GC_THRESHOLD0
        assert gc.get_freeze_count() == 0
        win.viewport._last_pos = None
        win._on_autosave_tick()                             # a collection, no freeze
        assert gc.get_freeze_count() == 0
    finally:
        gc.set_threshold(*old)
        win._saved_version = win.viewport.scene.version
        win.close()
