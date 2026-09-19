# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""Pulling a box up with the camera at ground level: the pull froze at the
horizon and the click on the box's top never fixed the height.

Rafael, 2026-09-16 (0:40–1:10): «te bloquea aquí, no te deja seguir un
poco más… hago clic aquí [sobre la cara superior] para que quede fijado,
que es lo que todo el mundo haría… no me deja. Tengo que venirme al
lateral del objeto y hacer clic ahí para que quede fijo».

Both are one thing. The viewport turns every pixel into a world point by
hitting a plane — for Push/Pull mid-drag, the face under the cursor or
the ground — and when the ray misses (above the horizon, or grazing the
ground at a low camera) it builds no context and the tool hears NOTHING:
no hover (the box freezes), no click (the top is where the cursor is, so
that click is lost; the side is below the horizon, so that one arrives).
The distance itself never needed the plane: it is read off the pixel
along the push axis. So the tool now offers the viewport a plane that
contains that axis and faces the camera (``Tool.drag_plane``), which the
ray always hits.
"""
from __future__ import annotations

import math
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QMouseEvent, QVector3D
from PySide6.QtWidgets import QApplication

_app = QApplication.instance() or QApplication([])


def _ground_level_pull():
    """Rafael's setup: camera 6° above the ground looking along the model,
    an 8 × 5 rectangle on the ground, Push/Pull engaged on it."""
    from views.main_window import MainWindow
    win = MainWindow()
    win.show()
    win.resize(1600, 900)
    _app.processEvents()
    vp = win.viewport
    cam = vp.camera
    cam.target = QVector3D(4, 2.5, 0)
    cam.distance = 18.0
    cam.pitch = math.radians(6.0)
    cam.yaw = math.radians(-60.0)
    face = vp.scene.mesh.add_face([QVector3D(0, 0, 0), QVector3D(8, 0, 0),
                                   QVector3D(8, 5, 0), QVector3D(0, 5, 0)])
    vp.scene.version += 1
    vp.update()
    _app.processEvents()
    win._activate_tool("pushpull")
    return win, vp, face


def _hover(vp, px, py):
    vp._last_mouse_pos = QPointF(px, py)
    vp._process_hover(QPointF(px, py), Qt.NoModifier)


def _click(vp, px, py):
    vp._last_mouse_pos = QPointF(px, py)
    vp._dispatch_tool_click(QMouseEvent(
        QMouseEvent.MouseButtonPress, QPointF(px, py),
        Qt.LeftButton, Qt.LeftButton, Qt.NoModifier))


def test_the_pull_follows_the_cursor_past_the_horizon_and_the_top_click_commits():
    win, vp, face = _ground_level_pull()
    try:
        tool = vp.active_tool
        cx, cy = vp._world_to_pixel(QVector3D(4, 2.5, 0))
        _hover(vp, cx, cy)
        assert tool.hovered_face is face
        _click(vp, cx, cy)
        assert tool.dragging
        # The cursor climbs; above the horizon the ground no longer answers
        # (the old failure), yet the extrusion keeps growing.
        heights = []
        for dy in (40, 120, 200, 280, 360, 400):
            _hover(vp, cx, cy - dy)
            heights.append(tool.extrusion)
        assert heights == sorted(heights) and heights[0] > 0.3
        assert heights[-1] > 5.0, heights
        # Click ON THE TOP of the box being pulled — where Rafael clicks.
        px, py = vp._world_to_pixel(QVector3D(4, 2.5, tool.extrusion))
        assert py < cy - 300                  # well above the horizon
        _hover(vp, px, py)
        _click(vp, px, py)
        assert not tool.dragging
        assert len(vp.scene.mesh.faces) == 6  # the box is committed
        top = max(v.position.z() for v in vp.scene.mesh.vertices)
        assert top > 5.0
    finally:
        win._saved_version = vp.scene.version
        win.close()


def test_drag_plane_contains_the_push_axis_and_faces_the_camera():
    from types import SimpleNamespace
    from tools.pushpull import PushPullTool

    tool = PushPullTool()
    cam = SimpleNamespace(target=QVector3D(0, 0, 0),
                          eye=lambda: QVector3D(10, -6, 3))
    vp = SimpleNamespace(camera=cam)
    assert tool.drag_plane(vp) is None            # idle: the viewport decides
    tool.dragging = True
    tool._anchor = QVector3D(1, 2, 0)
    tool._normal = QVector3D(0, 0, 1)
    point, normal = tool.drag_plane(vp)
    assert point == tool._anchor
    assert abs(QVector3D.dotProduct(normal, tool._normal)) < 1e-9
    forward = (cam.target - cam.eye()).normalized()
    assert QVector3D.dotProduct(normal, forward) > 0.9
    # Looking straight along the axis there is no such plane: fall back.
    cam.target = QVector3D(1, 2, 0)
    cam.eye = lambda: QVector3D(1, 2, 30)
    assert tool.drag_plane(vp) is None
