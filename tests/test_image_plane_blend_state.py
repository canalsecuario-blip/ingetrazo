# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""A faded reference image must not switch the frame's blending off: the
shadow catcher that follows writes alpha 0 where the sun reaches, and
without blending that is a transparent hole the size of the model's
shadow square — white on screen, and only on frames that REUSE the
cached shadow map (orbit, zoom), since a rebuild re-enables blending on
its way out. Marco, 2026-09-14: «puse sombras con el tif activo y orbité».

Needs a GL context; skipped where the offscreen platform has none."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest
from PySide6.QtGui import QImage, QVector3D
from PySide6.QtWidgets import QApplication

_app = QApplication.instance() or QApplication([])


def _alpha_zero_share(img: QImage) -> float:
    img = img.convertToFormat(QImage.Format_RGBA8888)
    buf = np.frombuffer(img.constBits(), np.uint8)
    px = buf.reshape(img.height(), img.bytesPerLine())[:, :img.width() * 4]
    return float((px.reshape(img.height(), img.width(), 4)[..., 3] == 0).mean())


def test_a_translucent_image_leaves_blending_on_for_the_shadow_catcher(tmp_path):
    from core.image_plane import ImagePlane
    from views.main_window import MainWindow

    win = MainWindow()
    try:
        win.show()
        _app.processEvents()
        vp = win.viewport
        if getattr(vp, "_gl", None) is None or not vp.isValid():
            pytest.skip("no OpenGL context on this platform")
        scene = vp.scene
        V = QVector3D
        scene.mesh.add_face([V(0, 0, 0), V(4, 0, 0), V(4, 4, 0), V(0, 4, 0)])
        scene.mesh.add_face([V(1, 1, 2), V(3, 1, 2), V(3, 3, 2), V(1, 3, 2)])
        pic = QImage(8, 8, QImage.Format_RGBA8888)
        pic.fill(0xFF3060A0)
        path = tmp_path / "scan.png"
        pic.save(str(path))
        scene.image_planes.append(ImagePlane(
            str(path), V(-20, -20, 0), V(40, 0, 0), V(0, 40, 0), opacity=0.5))
        scene.shadows.enabled = True
        scene.shadows.hour = 12
        scene.version += 1
        vp.camera.set_view("iso")
        vp.camera.fit_to(V(-20, -20, 0), V(20, 20, 2))
        first = vp.render_image(160, 120, overlays=False)     # rebuilds the map
        second = vp.render_image(160, 120, overlays=False)    # reuses it
        assert first is not None and second is not None
        assert _alpha_zero_share(first) == 0.0
        assert _alpha_zero_share(second) == 0.0
    finally:
        win._saved_version = win.viewport.scene.version
        win.close()
