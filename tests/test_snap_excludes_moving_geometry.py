# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""What Move / Rotate drag is left out of the snap candidates (issue #19).

SketchUp excludes the entities in motion from inference. Ours fed the snap
engine the whole scene, so dragging a face along a wall snapped to the face's
own (moving) corners — "self inference", as @pacaeiro named it.
"""
from __future__ import annotations

import os

import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QVector3D

from core.history import History
from core.scene import Scene
from tools.base import ToolContext
from tools.move import MoveTool
from tools.rotate import RotateTool


def V(x, y, z=0.0):
    return QVector3D(float(x), float(y), float(z))


class _Vp:
    def __init__(self, scene):
        self.scene = scene
        self.history = History(scene)

    def update(self):
        pass

    def flash_status(self, *a, **k):
        pass

    def pick_edge(self, x, y):
        return None

    def pick_face(self, x, y):
        return None

    def pick_group(self, x, y):
        return None


def _ctx(vp, x, y, z=0.0):
    return ToolContext(viewport=vp, world=V(x, y, z), screen=QPointF(0, 0),
                       modifiers=Qt.NoModifier, snap=None)


def test_move_names_the_edges_it_drags():
    scene = Scene()
    moving = scene.mesh.add_face([V(0, 0), V(1, 0), V(1, 1), V(0, 1)])
    still = scene.mesh.add_face([V(3, 0), V(4, 0), V(4, 1), V(3, 1)])
    scene.selection = [moving]
    vp = _Vp(scene)
    tool = MoveTool()
    assert tool.snap_excluded() is None                 # nothing in motion yet
    tool.on_click(_ctx(vp, 0, 0))
    edges, groups = tool.snap_excluded()
    assert groups == set()
    moving_ids = {id(e) for e in scene.mesh.edges
                  if any(v in moving.vertices for v in (e.a, e.b))}
    assert edges == moving_ids
    assert not any(id(e) in edges for e in scene.mesh.edges
                   if e.a in still.vertices and e.b in still.vertices)


def test_a_copy_in_progress_excludes_nothing():
    scene = Scene()
    scene.selection = [scene.mesh.add_face([V(0, 0), V(1, 0), V(1, 1), V(0, 1)])]
    vp = _Vp(scene)
    tool = MoveTool()
    tool.on_click(_ctx(vp, 0, 0))
    tool.on_key(vp, Qt.Key_Control, Qt.NoModifier)
    assert tool.snap_excluded() is None                 # the original stays put


def test_rotate_names_the_geometry_swinging():
    scene = Scene()
    scene.selection = [scene.mesh.add_face([V(0, 0), V(1, 0), V(1, 1), V(0, 1)])]
    vp = _Vp(scene)
    tool = RotateTool()
    tool.on_click(_ctx(vp, 0, 0))                       # centre
    assert tool.snap_excluded() is None                 # not swinging yet
    tool.on_click(_ctx(vp, 1, 0))                       # base arm
    edges, _groups = tool.snap_excluded()
    assert len(edges) == 4


def test_the_viewport_drops_the_moving_edges_from_the_snap_scene():
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    elif not isinstance(app, QApplication):
        pytest.skip("another Qt application flavour is already running")
    from views.viewport import Viewport
    vp = Viewport(None)
    vp.resize(1000, 600)
    vp.camera.set_aspect(1000, 600)
    vp.flash_status = lambda *a, **k: None
    vp.camera.set_view("top")
    vp.camera.target = V(2, 0.5, 0)
    vp.camera.distance = 12
    moving = vp.scene.mesh.add_face([V(0, 0), V(1, 0), V(1, 1), V(0, 1)])
    still = vp.scene.mesh.add_face([V(3, 0), V(4, 0), V(4, 1), V(3, 1)])
    vp.scene.version += 1
    vp.scene.selection.clear()
    vp.scene.selection.add(moving)
    tool = MoveTool()
    vp.set_active_tool(tool)
    px = vp._world_to_pixel(V(3, 0, 0))
    before = vp._snap_scene(*px).edges
    assert len(before) == 8                             # both squares, untouched
    tool.on_click(ToolContext(viewport=vp, world=V(0, 0, 0), screen=QPointF(0, 0),
                              modifiers=Qt.NoModifier, snap=None))
    during = vp._snap_scene(*px).edges
    assert len(during) == 4
    assert all(e.a in still.vertices and e.b in still.vertices for e in during)
    tool.on_cancel(vp)
    assert len(vp._snap_scene(*px).edges) == 8
