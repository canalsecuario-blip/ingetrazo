# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""A planar shape started on a free point follows the view (Rafael's review
of 2026-09-10, B1/B2).

At eye level, with the horizon mid-screen, his rectangle read «5.74 × 0.00 m»:
the viewport handed the second corner on the camera-facing VERTICAL plane
through the first (the near-horizon plane) while the tool measured the sides
along world X/Y — one side was always zero, at any cursor height. SketchUp's
rectangle, circle and arcs lay themselves out on the plane most perpendicular
to the view when nothing else decides; orbiting re-decides. Now the shape is
laid out on the plane of the last hit (``PlaneLock.hover_plane``), and the
near-horizon escape hatch — meant for the Line tool to draw upward — leaves
captured planes of PLANAR tools alone.
"""
from __future__ import annotations

import math

import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QVector3D
from PySide6.QtWidgets import QApplication

from tools.base import ToolContext


@pytest.fixture(scope="module")
def viewport():
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
    return vp


def _eye_level(vp, yaw_deg=20.0):
    """Rafael's camera: 1.6 m up, looking level (horizon mid-screen)."""
    cam = vp.camera
    cam.target = QVector3D(0, 0, 1.6)
    cam.distance = 12.0
    cam.pitch = 0.0
    cam.yaw = math.radians(yaw_deg)


def _ctx(vp, world, px):
    return ToolContext(viewport=vp, world=world, screen=QPointF(*px),
                       modifiers=Qt.NoModifier, snap=None)


def _hover_at(vp, tool, px):
    world = vp._world_from_pixel(int(px[0]), int(px[1]))
    assert world is not None
    tool.on_hover(_ctx(vp, world, px))
    return world


def _start_at_origin(vp, tool):
    vp.active_tool = tool
    o_px = vp._world_to_pixel(QVector3D(0, 0, 0))
    world = vp._world_from_pixel(int(o_px[0]), int(o_px[1]))
    tool.on_click(_ctx(vp, world, o_px))
    return o_px


def _span(points):
    lo = QVector3D(*[min(getattr(p, i)() for p in points) for i in ("x", "y", "z")])
    hi = QVector3D(*[max(getattr(p, i)() for p in points) for i in ("x", "y", "z")])
    return hi - lo


def test_rectangle_at_eye_level_stands_up_with_two_real_sides(viewport):
    from tools.rectangle import RectangleTool
    _eye_level(viewport)
    tool = RectangleTool()
    o_px = _start_at_origin(viewport, tool)
    assert tool.work_plane is None                      # free point: no capture
    horizon_y = viewport._world_to_pixel(QVector3D(0, 0, 1.6))[1]
    _hover_at(viewport, tool, (o_px[0] - 250, horizon_y - 34))   # Rafael's cursor
    text, _mid = tool.value_label()
    w, h = (float(t) for t in text.replace(" m", "").split(" × ")[:2])
    assert w > 1.0 and h > 1.0, text                    # not «5.74 × 0.00»
    corners = tool._corners(tool.start_point, tool.hover_point)
    span = _span(corners)
    assert span.z() > 1.0                               # it stands up
    assert min(span.x(), span.y()) < 1e-6               # in ONE vertical plane


def test_orbiting_after_the_first_click_re_decides_the_plane(viewport):
    from tools.rectangle import RectangleTool
    _eye_level(viewport)
    tool = RectangleTool()
    o_px = _start_at_origin(viewport, tool)
    horizon_y = viewport._world_to_pixel(QVector3D(0, 0, 1.6))[1]
    _hover_at(viewport, tool, (o_px[0] - 250, horizon_y + 40))
    assert _span(tool._corners(tool.start_point, tool.hover_point)).z() > 0.5
    viewport.camera.set_view("iso")                     # orbit up
    o_px = viewport._world_to_pixel(QVector3D(0, 0, 0))
    _hover_at(viewport, tool, (o_px[0] - 120, o_px[1] - 60))
    corners = tool._corners(tool.start_point, tool.hover_point)
    assert _span(corners).z() < 1e-6                    # flat on the ground again
    assert _span(corners).x() > 0.5 and _span(corners).y() > 0.1


def test_circle_at_eye_level_stands_up(viewport):
    from tools.circle import CircleTool
    _eye_level(viewport, yaw_deg=80.0)
    tool = CircleTool()
    o_px = _start_at_origin(viewport, tool)
    horizon_y = viewport._world_to_pixel(QVector3D(0, 0, 1.6))[1]
    _hover_at(viewport, tool, (o_px[0] - 150, horizon_y - 20))
    pts = tool._points(tool.start_point, tool.hover_point)
    span = _span(pts)
    assert span.z() > 1.0 and min(span.x(), span.y()) < 1e-6


def test_a_captured_slab_keeps_a_planar_tool_flat_at_the_horizon(viewport):
    """The near-horizon escape hatch (a horizontal captured plane yields to a
    vertical one so a LINE can rise) must not touch a rectangle's captured
    plane: its corners live in that plane by definition."""
    from tools.rectangle import RectangleTool
    _eye_level(viewport)
    tool = RectangleTool()
    tool.start_point = QVector3D(0, 0, 0)
    tool.work_plane = (QVector3D(0, 0, 0), QVector3D(0, 0, 1))   # clicked a slab
    viewport.active_tool = tool
    _pt, n = viewport._current_work_plane()
    assert abs(n.z()) > 0.99

    class _Line:                                        # a line-like tool
        start_point = QVector3D(0, 0, 0)
        work_plane = (QVector3D(0, 0, 0), QVector3D(0, 0, 1))
    viewport.active_tool = _Line()
    _pt, n = viewport._current_work_plane()
    assert abs(n.z()) < 1e-6                            # still rises for a line


# ---------------------------------------------------------------------------
# SketchUp shows the plane on the cursor BEFORE the first click: a ring (circle,
# polygon) or a little square (rectangle) lying on the plane the shape would
# take, drawn in the axis colour while an arrow key locks it. Without it our
# lock was invisible — Rafael: «sí que me cambia de plano, pero no se ve».

def _plane_of(segments):
    return _span([a for a, _b in segments])


def test_circle_shows_a_ring_on_the_cursor_in_the_locked_plane_colour(viewport):
    from tools.base import PLANE_LOCK_KEYS
    from tools.circle import CircleTool
    from core.snap import AXIS_COLORS
    viewport.camera.set_view("iso")
    tool = CircleTool()
    viewport.active_tool = tool
    key = next(k for k, a in PLANE_LOCK_KEYS.items() if a == "y")   # Left = green
    tool.on_key(viewport, key, None)
    px = (500, 300)
    world = viewport._world_from_pixel(*px)
    tool.on_hover(_ctx(viewport, world, px))
    segs = tool.rubber_band_lines()
    assert len(segs) == tool.sides                     # a ring, before any click
    span = _plane_of(segs)
    assert span.y() < 1e-6 and span.x() > 0 and span.z() > 0   # normal to green
    assert tool.wireframe_color[:3] == tuple(AXIS_COLORS["y"][:3])
    r_px = viewport._world_to_pixel(segs[0][0])
    c_px = viewport._world_to_pixel(world)
    assert abs(math.hypot(r_px[0] - c_px[0], r_px[1] - c_px[1]) - tool.PREVIEW_PX) < 4
    tool.on_key(viewport, key, None)                   # the same key frees it
    tool.on_hover(_ctx(viewport, world, px))
    assert tool.wireframe_color is None
    assert _plane_of(tool.rubber_band_lines()).z() < 1e-6        # flat on the ground


def test_rectangle_shows_a_square_on_the_cursor_and_keeps_the_colour_while_drawing(viewport):
    from tools.base import PLANE_LOCK_KEYS
    from tools.rectangle import RectangleTool
    viewport.camera.set_view("iso")
    tool = RectangleTool()
    viewport.active_tool = tool
    px = (500, 300)
    world = viewport._world_from_pixel(*px)
    tool.on_hover(_ctx(viewport, world, px))
    segs = tool.rubber_band_lines()
    assert len(segs) == 4 and _plane_of(segs).z() < 1e-6          # flat square glyph
    assert tool.wireframe_color is None
    key = next(k for k, a in PLANE_LOCK_KEYS.items() if a == "x")   # Right = red
    tool.on_key(viewport, key, None)
    tool.on_hover(_ctx(viewport, world, px))
    assert _plane_of(tool.rubber_band_lines()).x() < 1e-6          # normal to red
    red = tool.wireframe_color
    tool.on_click(_ctx(viewport, world, px))
    tool.on_hover(_ctx(viewport, world + QVector3D(0, 1, 1), px))
    assert tool.wireframe_color == red                 # still red while drawing
    assert _plane_of(tool.rubber_band_lines()).x() < 1e-6
    tool._reset()
    assert tool.wireframe_color is None and tool.plane_lock is None


def test_a_zero_sided_rectangle_is_refused_instead_of_raising(viewport):
    """Marco's log (2026-09-14): «degenerate edge: endpoints weld to one
    vertex» from the history — the second corner sat on the first's row.
    SketchUp draws nothing; we say why."""
    from tools.rectangle import RectangleTool
    viewport.camera.set_view("iso")
    said = []
    viewport.flash_status = lambda text, *a, **k: said.append(text)
    tool = RectangleTool()
    viewport.active_tool = tool
    before = len(viewport.scene.mesh.edges)
    tool.on_click(_ctx(viewport, QVector3D(0, 0, 0), (0, 0)))
    tool.on_click(_ctx(viewport, QVector3D(3, 0, 0), (0, 0)))    # same row: no height
    assert len(viewport.scene.mesh.edges) == before
    assert said and "two sides" in said[-1]
    viewport.flash_status = lambda *a, **k: None
