# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""The unsaved-changes question is Qt's own dialog, never the native one.

On macOS the native alert drew «Don't Save» as red destructive text on a
black button under the app's forced dark scheme — barely readable."""
from __future__ import annotations

from PySide6.QtWidgets import QApplication, QMessageBox

_app = QApplication.instance() or QApplication([])


def test_the_unsaved_changes_box_is_drawn_by_qt(monkeypatch):
    from views.main_window import MainWindow
    seen = []

    def fake_exec(box):
        seen.append((box.testOption(QMessageBox.Option.DontUseNativeDialog),
                     box.standardButtons(), box.defaultButton()))
        return QMessageBox.Discard

    monkeypatch.setattr(QMessageBox, "exec", fake_exec)
    win = MainWindow()
    win.viewport.scene.version += 1               # something unsaved
    assert win._confirm_discard("Quit IngeTrazo?") is True
    native_off, buttons, default = seen[0]
    assert native_off
    assert buttons == (QMessageBox.Save | QMessageBox.Discard
                       | QMessageBox.Cancel)
    assert default is not None and default.text()  # Save is the default
    win._saved_version = win.viewport.scene.version
