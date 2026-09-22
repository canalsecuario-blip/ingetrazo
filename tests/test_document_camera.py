# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""Issue #60 (@pacaeiro): «If I do a New drawing, or open a drawing, the
Camera stays in the position where it was before». The .igz now keeps the
camera it was saved with; New goes back to the default view."""
from __future__ import annotations

import math
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QVector3D  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

if QApplication.instance() is None:
    QApplication([])

from core.scene import Scene  # noqa: E402
from formats import igz  # noqa: E402


def test_the_camera_travels_in_the_igz(tmp_path):
    scene = Scene()
    scene.camera_home = {"target": [1.0, 2.0, 3.0], "distance": 7.5,
                         "yaw": 0.3, "pitch": 0.4, "fov_deg": 50.0,
                         "perspective": False}
    path = tmp_path / "cam.igz"
    igz.save_scene(scene, path)
    back = Scene()
    igz.load_into(back, path)
    assert back.camera_home == scene.camera_home
    scene.clear()
    assert scene.camera_home is None


def test_open_restores_the_authors_view_and_new_resets_it(tmp_path):
    from views.main_window import MainWindow
    win = MainWindow()
    try:
        cam = win.viewport.camera
        win._saved_version = win.viewport.scene.version
        cam.target = QVector3D(12.0, -4.0, 1.5)
        cam.distance = 33.0
        cam.yaw = 1.1
        cam.pitch = 0.2
        cam.perspective = False
        path = tmp_path / "doc.igz"
        win._do_save(path)
        assert win.viewport.scene.camera_home["distance"] == 33.0
        # Move the camera away, then reopen: back where the author left it.
        cam.target = QVector3D(0, 0, 0)
        cam.distance = 5.0
        cam.yaw = -0.7
        cam.perspective = True
        win._saved_version = win.viewport.scene.version
        assert win.open_path(path)
        assert (cam.target - QVector3D(12.0, -4.0, 1.5)).length() < 1e-6
        assert cam.distance == 33.0 and abs(cam.yaw - 1.1) < 1e-9
        assert cam.perspective is False
        # New: the default view, whatever the last document did.
        win._saved_version = win.viewport.scene.version
        win._on_new()
        assert cam.distance == 20.0 and cam.perspective is True
        assert abs(cam.yaw - math.radians(-45.0)) < 1e-9
        assert (cam.target - QVector3D(0, 0, 0)).length() < 1e-9
    finally:
        win._saved_version = win.viewport.scene.version
        win.close()
