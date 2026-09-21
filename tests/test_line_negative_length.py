# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""Line tool VCB: a negative length runs the opposite way (issue #58,
@pacaeiro: «Command LINE do not accept negative values. It should work as
Move/Copy, by inverting the direction of the vector»)."""
from __future__ import annotations

from PySide6.QtGui import QVector3D

from core.history import History
from core.scene import Scene
from tools.line import LineTool


class _Vp:
    def __init__(self, scene):
        self.scene = scene
        self.history = History(scene)

    def update(self):
        pass

    def flash_status(self, *a, **k):
        pass


def _edges(scene):
    return [(e.a, e.b) for e in scene.mesh.edges]


def test_negative_length_runs_away_from_the_cursor():
    scene = Scene()
    vp = _Vp(scene)
    t = LineTool()
    t.start_point = QVector3D(0, 0, 0)
    t.hover_point = QVector3D(1, 0, 0)              # rubber band along +X
    assert t.on_value(vp, -2.0) is True
    (a, b), = _edges(scene)
    assert (a - QVector3D(0, 0, 0)).length() < 1e-9
    assert (b - QVector3D(-2, 0, 0)).length() < 1e-9   # the other way
    assert (t.start_point - QVector3D(-2, 0, 0)).length() < 1e-9  # chain goes on


def test_zero_length_is_still_refused():
    scene = Scene()
    vp = _Vp(scene)
    t = LineTool()
    t.start_point = QVector3D(0, 0, 0)
    t.hover_point = QVector3D(1, 0, 0)
    assert t.on_value(vp, 0.0) is False
    assert not _edges(scene)
