# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""What Move drags does not hide snaps behind it.

The live preview moves the selection in the scene, and the occlusion rays
hit it: sliding a rectangle across a wall hid the wall's corners and edges
under the rectangle, and their inferences showed only in X-ray (Marco,
2026-09-29). Snaps are inferred through the entities in motion, as they are
already left out of the candidates (issue #19)."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QVector3D as V
from PySide6.QtWidgets import QApplication

from tools.base import ToolContext
from tools.move import MoveTool


@pytest.fixture
def vp():
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
    vp.camera.set_view("front")                          # looking toward +Y
    vp.camera.target = V(0, 0, 1)
    vp.camera.distance = 12
    return vp


def _scene(vp):
    """A wall on Y=0 and, 0.3 m in front of it, a loose rectangle that
    covers the wall point (0, 0, 1)."""
    sc = vp.scene
    sc.mesh.add_face([V(-3, 0, 0), V(3, 0, 0), V(3, 0, 3), V(-3, 0, 3)])
    rect = sc.mesh.add_face([V(-1, -0.3, 0.5), V(1, -0.3, 0.5),
                             V(1, -0.3, 1.5), V(-1, -0.3, 1.5)])
    sc.version += 1
    return rect


def _grab(vp, tool, at):
    tool.on_click(ToolContext(viewport=vp, world=at, screen=QPointF(0, 0),
                              modifiers=Qt.NoModifier, snap=None))


def test_the_rectangle_being_moved_does_not_hide_the_wall(vp):
    rect = _scene(vp)
    on_wall = V(0, 0, 1)
    assert vp._is_occluded(on_wall)                      # standing still, it hides
    vp.scene.selection.clear()
    vp.scene.selection.add(rect)
    tool = MoveTool()
    vp.set_active_tool(tool)
    _grab(vp, tool, V(-1, -0.3, 0.5))
    assert not vp._is_occluded(on_wall)                  # in motion, it doesn't
    tool.on_cancel(vp)
    assert vp._is_occluded(on_wall)                      # dropped back, it hides


def test_a_group_being_moved_does_not_hide_the_wall(vp):
    # A group drags through the viewport's preview, not the scene: its faces
    # stay in the pick index where they were, and hid the wall from there.
    from core.history import History, MakeGroupCommand
    rect = _scene(vp)
    History(vp.scene).execute(MakeGroupCommand([rect], []))
    vp.scene.version += 1
    group = vp.scene.groups[0]
    # The preview itself only paints (GL); without it the index is what the
    # app has during the drag.
    vp.begin_groups_preview = lambda groups=(), external=False: None
    vp.set_groups_preview_offset = lambda delta: None
    vp.end_groups_preview = lambda: None
    on_wall = V(0, 0, 1)
    assert vp._is_occluded(on_wall)
    vp.scene.selection.clear()
    vp.scene.selection.add(group)
    tool = MoveTool()
    vp.set_active_tool(tool)
    _grab(vp, tool, V(-1, -0.3, 0.5))
    assert not vp._is_occluded(on_wall)
    tool.on_cancel(vp)
    assert vp._is_occluded(on_wall)


def test_what_stays_put_still_hides(vp):
    rect = _scene(vp)
    # A second face in front, not selected: it keeps hiding the wall while
    # the rectangle moves.
    vp.scene.mesh.add_face([V(-0.5, -1, 0.8), V(0.5, -1, 0.8),
                            V(0.5, -1, 1.2), V(-0.5, -1, 1.2)])
    vp.scene.version += 1
    vp.scene.selection.clear()
    vp.scene.selection.add(rect)
    tool = MoveTool()
    vp.set_active_tool(tool)
    _grab(vp, tool, V(-1, -0.3, 0.5))
    assert vp._is_occluded(V(0, 0, 1))
    tool.on_cancel(vp)
