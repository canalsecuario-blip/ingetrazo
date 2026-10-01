# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""Issue #184 (Alejandro Limón, by email): «El pan se vuelve muy lento con
la cámara en su acercamiento mínimo.» The pan moved by the distance to the
orbit target, which zooming in shrinks to 2 cm, whatever lay under the
cursor. Now it moves by the depth of the point grabbed, so that point
stays under the cursor — in perspective; parallel views scale
the same everywhere."""
from __future__ import annotations

import math

import pytest
from PySide6.QtGui import QVector3D, QVector4D

from core.camera import MIN_DISTANCE, OrbitCamera

W, H = 1000, 700


def _screen_x(cam, p):
    clip = (cam.projection_matrix() * cam.view_matrix()).map(
        QVector4D(p.x(), p.y(), p.z(), 1.0))
    return (clip.x() / clip.w() * 0.5 + 0.5) * W


def _cam(perspective=True):
    cam = OrbitCamera()
    cam.set_aspect(W, H)
    cam.perspective = perspective
    cam.target = QVector3D(0, 0, 0)
    cam.distance = MIN_DISTANCE                  # zoomed all the way in
    return cam


def test_the_grabbed_point_follows_the_cursor_at_full_zoom():
    cam = _cam()
    wall = cam.eye() + cam.forward() * 5.0       # a wall 5 m in front
    right = QVector3D.crossProduct(cam.forward(), cam.up_vector()).normalized()
    wall = wall + right * 0.5                    # a bit off-centre
    depth = QVector3D.dotProduct(wall - cam.eye(), cam.forward())
    x0 = _screen_x(cam, wall)
    cam.pan(100, 0, H, depth=depth)
    assert _screen_x(cam, wall) - x0 == pytest.approx(100.0, abs=0.5)


def test_without_a_depth_it_was_a_crawl():
    """The old behaviour, pinned so the difference stays visible: the same
    100 px moved the 5 m wall by well under one pixel."""
    cam = _cam()
    wall = cam.eye() + cam.forward() * 5.0
    x0 = _screen_x(cam, wall)
    cam.pan(100, 0, H)
    assert abs(_screen_x(cam, wall) - x0) < 1.0


def test_parallel_views_ignore_the_depth():
    a, b = _cam(False), _cam(False)
    a.distance = b.distance = 10.0
    a.pan(100, 40, H)
    b.pan(100, 40, H, depth=250.0)
    assert (a.target - b.target).length() < 1e-9


@pytest.mark.parametrize("bad", [None, 0.0, -3.0, math.inf, math.nan])
def test_a_useless_depth_falls_back_to_the_target(bad):
    a, b = _cam(), _cam()
    a.distance = b.distance = 4.0
    a.pan(50, 20, H)
    b.pan(50, 20, H, depth=bad)
    assert (a.target - b.target).length() < 1e-9
