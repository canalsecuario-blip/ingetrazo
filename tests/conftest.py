# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""One full QApplication for the whole test session, created BEFORE any test
module imports. Test files that need widgets (MainWindow, the tray) and
files that only need fonts used to create their own app at import time —
a QGuiApplication first meant every later widget test aborted, so the
outcome depended on which files were on the command line."""
import os
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication  # noqa: E402

if QApplication.instance() is None:
    QApplication(sys.argv[:1])

# And a QSettings store of its own, thrown away with the session. The suite
# is not read-only about preferences: a test that exercises «new items
# inherit the last style» writes that style out, so it landed in the
# developer's real settings and POISONED ITS OWN NEXT RUN — the cota style
# test placed a cota with text_pos="below" and then failed the next day
# asserting "above". Isolating the store makes every run start from the
# same place, here and on the CI runner.
import tempfile  # noqa: E402

from PySide6.QtCore import QSettings  # noqa: E402

_settings_dir = tempfile.mkdtemp(prefix="ingetrazo-tests-settings-")
QSettings.setDefaultFormat(QSettings.IniFormat)
for scope in (QSettings.UserScope, QSettings.SystemScope):
    QSettings.setPath(QSettings.IniFormat, scope, _settings_dir)


import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def _world_drawing_axes():
    """The drawing axes are process-wide (core.axes, issue #44): a test that
    leaves a turned group open must not tilt the next one's inferences."""
    from core import axes
    axes.sync(None)
    yield
    axes.sync(None)
