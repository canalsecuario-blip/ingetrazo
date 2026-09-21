# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""The Line tool's axis magnet reaches the other drawing tools (issue #52,
@pacaeiro: «The Draw commands in the group of ARCS and SHAPES should also
use the magnetic Snaps, like LINE. Except Freehand»; #51 Text; #50 the
Dimension's measured span) — and switches itself off for the clicks that
are not a direction from the start point."""
from __future__ import annotations

from types import SimpleNamespace

from PySide6.QtGui import QVector3D

from core.snap import compute_snap
from tools.arc import ArcTool, CenterArcTool, ThreePointArcTool
from tools.circle import CircleTool, PolygonTool
from tools.dimension import DimensionTool
from tools.freehand import FreehandTool
from tools.line import LineTool
from tools.rectangle import RectangleTool
from tools.rotated_rectangle import RotatedRectangleTool
from tools.text import TextTool


def V(x, y, z=0.0):
    return QVector3D(float(x), float(y), float(z))


def _magnet(tool):
    return (getattr(tool, "magnetic_axis_deg", None),
            getattr(tool, "screen_axis_px", None))


def test_the_shapes_declare_the_line_tools_magnet():
    line = _magnet(LineTool())
    assert line == (3.0, 9.0)
    for cls in (ArcTool, ThreePointArcTool, CenterArcTool, CircleTool,
                PolygonTool, RotatedRectangleTool, TextTool, DimensionTool):
        assert _magnet(cls()) == line, cls.__name__


def test_freehand_and_rectangle_stay_out():
    assert _magnet(FreehandTool()) == (None, None)
    # The rectangle's second click is the opposite corner: a magnet aimed
    # at the first corner would flatten every thin rectangle near an axis.
    assert _magnet(RectangleTool()) == (None, None)


def test_the_magnet_is_off_for_clicks_that_are_not_a_direction_from_the_start():
    arc = ArcTool()
    arc.start_point = V(0, 0)
    assert _magnet(arc) == (3.0, 9.0)                 # the chord end
    arc.end_point = V(2, 0)
    assert _magnet(arc) == (None, None)               # the bulge
    rr = RotatedRectangleTool()
    rr.start_point = V(0, 0)
    assert _magnet(rr) == (3.0, 9.0)                  # the base edge
    rr.base_point = V(2, 0)
    assert _magnet(rr) == (None, None)                # the height
    dim = DimensionTool()
    dim.a = dim.start_point = V(0, 0)
    assert _magnet(dim) == (3.0, 9.0)                 # the measured span
    dim.b = V(2, 0)
    assert _magnet(dim) == (None, None)               # the placement


def _w2p(p):
    return (p.x() * 100.0, p.y() * 100.0 - p.z() * 100.0)


def test_a_circles_radius_point_lands_on_the_axis_through_the_engine():
    """The same call the viewport makes, with a circle's attributes: a
    rim point 2° off the red axis comes back ON it."""
    tool = CircleTool()
    tool.start_point = V(0, 0)
    start = tool.start_point
    cursor = V(2.0, 0.07)                             # 2° above +X
    snap = compute_snap(
        candidate_world=cursor, candidate_pixel=_w2p(cursor),
        scene=SimpleNamespace(edges=[]), world_to_pixel=_w2p,
        threshold_px=9.0, edge_threshold_px=14.0, start_point=start,
        project_onto_line=lambda s, d: s + d * QVector3D.dotProduct(cursor - s, d),
        magnetic_axis_deg=tool.magnetic_axis_deg,
        screen_axis_px=tool.screen_axis_px)
    assert snap.kind == "axis" and snap.axis == "x"
    assert abs(snap.point.y()) < 1e-6 and abs(snap.point.x() - 2.0) < 1e-6
