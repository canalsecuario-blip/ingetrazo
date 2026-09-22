# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""File ▸ Open Recent: the last documents, remembered across sessions,
newest first, missing ones dropped, imports never listed."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QSettings  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

if QApplication.instance() is None:
    QApplication([])


def test_recent_list_is_ordered_deduplicated_and_capped(tmp_path):
    from views.main_window import MainWindow
    win = MainWindow()
    try:
        QSettings().setValue("recent_files", [])
        docs = []
        for i in range(12):
            p = tmp_path / f"doc{i}.igz"
            p.write_text("{}")
            docs.append(p)
            win._remember_recent(p)
        recent = win._recent_paths()
        assert len(recent) == MainWindow._RECENT_MAX
        assert recent[0] == str(docs[-1].resolve())          # newest first
        win._remember_recent(docs[-3])                        # re-open an old one
        assert win._recent_paths()[0] == str(docs[-3].resolve())
        assert len(win._recent_paths()) == MainWindow._RECENT_MAX
        win._remember_recent(tmp_path / "modelo.skp")         # an import
        assert not any(x.endswith(".skp") for x in win._recent_paths())
        # A file deleted meanwhile is not offered.
        docs[-1].unlink()
        win._fill_recent_menu()
        labels = [a.text() for a in win._recent_menu.actions() if a.text()]
        assert not any("doc11.igz" in t for t in labels)
        assert any("doc9.igz" in t for t in labels)
        assert any("Clear" in t or "Limpiar" in t for t in labels)
    finally:
        QSettings().setValue("recent_files", [])
        win._saved_version = win.viewport.scene.version
        win.close()
