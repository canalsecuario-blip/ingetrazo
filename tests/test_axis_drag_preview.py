# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""The tilt drag shows what it is about to do (issue #25, @pacaeiro).

«Protractor and Rotate Click+Drag option could have live preview,
indicating that it is reacting to the mouse movement.» Dragging from the
vertex tilts the instrument off the inferred plane (issue #10), but nothing
on screen moved until the button came up — the gesture happened in the
dark and you only learned whether it had taken after letting go.

Now the disc tilts as the hand moves, and from the very same stored axis
the release commits, so the preview cannot promise one thing and deliver
another. The axis the tool COMMITS is untouched: this is drawing only.
"""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QVector3D

from core.history import History
from core.scene import Scene
from tools.base import ToolContext
from tools.protractor import ProtractorTool
from tools.rotate import RotateTool

V = QVector3D


class _Vp:
    """A stub with the one thing the drag threshold needs: a projection."""

    def __init__(self, scene):
        self.scene = scene
        self.history = History(scene)

    def update(self):
        pass

    def set_hover(self, *_a):
        pass

    def flash_status(self, *_a, **_k):
        pass

    def pick_group(self, x, y):
        return None

    def pick_edge(self, x, y):
        return None

    def pick_face(self, x, y):
        return None

    def _world_to_pixel(self, p):
        # A front elevation at 50 px per metre: X to the right, Z up. It has
        # to carry Z — the tilt drag is exactly the gesture that leaves the
        # ground plane, and a projection that drops Z measures it as zero.
        return (p.x() * 50.0, -p.z() * 50.0)


def _ctx(vp, x, y, z=0.0):
    return ToolContext(viewport=vp, world=V(float(x), float(y), float(z)),
                       screen=QPointF(0, 0), modifiers=Qt.NoModifier,
                       snap=None)


def _disc_normal(tool, vp):
    """The plane the drawn disc lies in, read back from its own segments."""
    segs = tool.rubber_band_lines()
    pts = [p for seg in segs[:24] for p in seg]
    c = tool.start_point
    best = None
    for i in range(len(pts)):
        for j in range(i + 1, len(pts)):
            n = QVector3D.crossProduct(pts[i] - c, pts[j] - c)
            if n.length() > 1e-6:
                best = n.normalized()
                break
        if best is not None:
            break
    return best


def _tools():
    for make in (ProtractorTool, RotateTool):
        scene = Scene()
        scene.mesh.add_face([V(0, 0, 0), V(1, 0, 0), V(1, 1, 0), V(0, 1, 0)])
        scene.selection = [scene.mesh.faces[0]]
        yield make(), _Vp(scene)


def test_the_disc_tilts_while_the_drag_is_happening():
    for tool, vp in _tools():
        tool.on_click(_ctx(vp, 0, 0))                   # press at the vertex
        flat = _disc_normal(tool, vp)
        assert flat is not None

        # Diagonal on purpose: a drag straight up would set the axis to
        # +Z, which is the plane the disc was already in.
        tool.on_hover(_ctx(vp, 2, 0, 2))                # 141 px: a real drag
        assert tool._axis_drag_live is not None, type(tool).__name__
        tilted = _disc_normal(tool, vp)
        assert tilted is not None
        # The disc is no longer in the plane it started in.
        assert abs(QVector3D.dotProduct(flat, tilted)) < 0.99, \
            type(tool).__name__


def test_a_move_too_small_to_count_shows_nothing():
    """Under the threshold the release keeps the inferred plane, so the
    preview must not promise a tilt."""
    for tool, vp in _tools():
        tool.on_click(_ctx(vp, 0, 0))
        tool.on_hover(_ctx(vp, 0.05, 0))                # 2.5 px at 50 px/m
        assert tool._axis_drag_live is None, type(tool).__name__


def test_the_release_commits_exactly_the_axis_the_preview_showed():
    for tool, vp in _tools():
        tool.on_click(_ctx(vp, 0, 0))
        tool.on_hover(_ctx(vp, 2, 0, 2))
        previewed = QVector3D(tool._axis_drag_live)
        tool.on_release(vp)
        assert tool._custom_axis is not None, type(tool).__name__
        assert (tool._custom_axis - previewed).length() < 1e-9, \
            type(tool).__name__
        assert tool._axis_drag_live is None      # the window closed


def test_a_plain_click_still_keeps_the_inferred_plane():
    for tool, vp in _tools():
        tool.on_click(_ctx(vp, 0, 0))
        tool.on_release(vp)                      # no move in between
        assert tool._custom_axis is None, type(tool).__name__
