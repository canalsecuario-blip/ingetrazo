# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""After a document loads, its objects are frozen out of the garbage
collector's incremental passes (1.3 M objects on the plaza; passes of up to
233 ms hit while drawing — Marco, 2026-09-14); the autosave tick re-settles."""
import gc
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtWidgets import QApplication

_app = QApplication.instance() or QApplication([])


def test_open_path_freezes_the_heap_and_the_tick_resettles(tmp_path):
    from views.main_window import MainWindow
    win = MainWindow()
    try:
        gc.unfreeze()
        assert gc.get_freeze_count() == 0
        win._on_new()
        assert gc.get_freeze_count() > 0                    # a fresh document settles too
        junk = [[i] for i in range(1000)]                   # session objects, collectable
        del junk
        win.viewport._last_pos = None
        win._on_autosave_tick()                             # re-settles: unfreeze → collect → freeze
        assert gc.get_freeze_count() > 0                    # (a few fewer: the collected junk)
        win.viewport._last_pos = (1, 1)                     # mid-gesture: leaves the heap alone
        before = gc.get_freeze_count()
        gc.unfreeze()
        win._on_autosave_tick()
        assert gc.get_freeze_count() == 0
        gc.freeze()
    finally:
        gc.unfreeze()
        win._saved_version = win.viewport.scene.version
        win.close()
