# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""A text prompt wide enough to read.

``QInputDialog.getText`` sizes itself to its contents, so a short label
gave a dialog a few centimetres wide whose title the window manager cut to
«Crear…» (Rafael, revision 4, 02:16 and 06:24). Same call, same answer,
with a sensible floor on the width.
"""
from __future__ import annotations

from PySide6.QtWidgets import QInputDialog, QLineEdit

#: Wide enough for a title like «Crear componente» and a name to edit.
MIN_WIDTH = 380

#: Qt's own static prompt, as imported. A test (or a plugin) that replaces
#: ``QInputDialog.getText`` to answer for the user is still obeyed.
_QT_GET_TEXT = QInputDialog.getText


def get_text(parent, title: str, label: str, echo=QLineEdit.Normal,
             text: str = "", **_ignored) -> tuple[str, bool]:
    """Drop-in for ``QInputDialog.getText`` returning ``(text, ok)``."""
    if QInputDialog.getText is not _QT_GET_TEXT:
        if echo == QLineEdit.Normal:
            return QInputDialog.getText(parent, title, label, text=text)
        return QInputDialog.getText(parent, title, label, echo, text=text)
    dlg = QInputDialog(parent)
    dlg.setWindowTitle(title)
    dlg.setLabelText(label)
    dlg.setTextEchoMode(echo)
    dlg.setTextValue(text)
    dlg.setMinimumWidth(MIN_WIDTH)
    dlg.resize(max(dlg.sizeHint().width(), MIN_WIDTH), dlg.sizeHint().height())
    ok = dlg.exec() == QInputDialog.Accepted
    return dlg.textValue(), ok
