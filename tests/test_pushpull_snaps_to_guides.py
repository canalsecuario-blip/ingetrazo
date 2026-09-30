# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""Push/Pull stops level with a Tape Measure guide (issue #165).

The usual way: you mark a height with the Tape -- a guide point above a corner,
or a guide line -- and push the face until it engages the guide. Ours never
engaged: the push's distance inference scanned mesh vertices, edges and faces,
and guides live in ``Scene.guides``, outside the mesh.
"""
from __future__ import annotations

import math
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QMouseEvent, QVector3D
from PySide6.QtWidgets import QApplication

from core.guide import Guide

_app = QApplication.instance() or QApplication([])


def _window():
    from views.main_window import MainWindow
    win = MainWindow()
    win.show()
    win.resize(1600, 900)
    _app.processEvents()
    vp = win.viewport
    cam = vp.camera
    cam.target = QVector3D(2, 2, 1.5)
    cam.distance = 16.0
    cam.pitch = math.radians(25.0)
    cam.yaw = math.radians(-50.0)
    face = vp.scene.mesh.add_face([QVector3D(0, 0, 0), QVector3D(4, 0, 0),
                                   QVector3D(4, 4, 0), QVector3D(0, 4, 0)])
    vp.scene.version += 1
    vp.update()
    _app.processEvents()
    return win, vp, face


def _hover(vp, px, py):
    vp._last_mouse_pos = QPointF(px, py)
    vp._process_hover(QPointF(px, py), Qt.NoModifier)


def _click(vp, px, py):
    vp._last_mouse_pos = QPointF(px, py)
    vp._dispatch_tool_click(QMouseEvent(
        QMouseEvent.MouseButtonPress, QPointF(px, py),
        Qt.LeftButton, Qt.LeftButton, Qt.NoModifier))


def _start_push(win, vp):
    win._activate_tool("pushpull")
    cx, cy = vp._world_to_pixel(QVector3D(2, 2, 0))
    _hover(vp, cx, cy)
    tool = vp.active_tool
    _click(vp, cx, cy)
    assert tool.dragging
    return tool


def _tape_guide_point(win, vp, height):
    """The Tape's own way: click a corner, aim up the blue axis, type."""
    win._activate_tool("tape")
    tape = vp.active_tool
    tape._mode = "point"
    x0, y0 = vp._world_to_pixel(QVector3D(4, 4, 0))
    _hover(vp, x0, y0)
    _click(vp, x0, y0)
    x1, y1 = vp._world_to_pixel(QVector3D(4, 4, 2.0))
    _hover(vp, x1, y1)
    assert tape.on_value(vp, height)
    points = [g for g in vp.scene.guides if g.direction is None]
    assert len(points) == 1, vp.scene.guides
    return points[0]


def test_push_stops_level_with_a_tape_guide_point():
    win, vp, face = _window()
    try:
        guide = _tape_guide_point(win, vp, 2.5)
        tool = _start_push(win, vp)
        gx, gy = vp._world_to_pixel(guide.point)
        _hover(vp, gx + 2, gy + 1)                   # a hair off the guide
        assert tool._inference_kind == "guide_point"
        assert abs(tool.extrusion - guide.point.z()) < 1e-9
        marker = tool.inference_marker()
        assert marker is not None and marker[1] == "guide_point"
        _click(vp, gx + 2, gy + 1)                   # commit
        tops = [f for f in vp.scene.mesh.faces
                if all(abs(v.z() - guide.point.z()) < 1e-9 for v in f.vertices)]
        assert tops, "no cap at the guide's height"
    finally:
        win._saved_version = win.viewport.scene.version
        win.close()


def test_push_stops_level_with_a_guide_line():
    win, vp, face = _window()
    try:
        # the kind of line the Tape pulls off an edge: along X, 3 m up
        line = Guide(QVector3D(0, 6, 3.0), QVector3D(1, 0, 0))
        vp.scene.guides.append(line)
        tool = _start_push(win, vp)
        lx, ly = vp._world_to_pixel(QVector3D(2, 6, 3.0))
        _hover(vp, lx + 1, ly + 2)
        assert tool._inference_kind == "guide_line"
        assert abs(tool.extrusion - 3.0) < 1e-9
    finally:
        win._saved_version = win.viewport.scene.version
        win.close()


def test_without_the_guide_the_push_follows_the_cursor():
    win, vp, face = _window()
    try:
        tool = _start_push(win, vp)
        target = QVector3D(4, 4, 2.5)
        gx, gy = vp._world_to_pixel(target)
        _hover(vp, gx + 2, gy + 1)
        assert tool._inference_kind != "guide_point"
        assert abs(tool.extrusion - 2.5) > 1e-6       # nothing to lock on
    finally:
        win._saved_version = win.viewport.scene.version
        win.close()
