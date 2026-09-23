# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""@pacaeiro, issue #70: «Rotated rectangle can improve with a "Protractor"
inside it». It is SketchUp's own tool: a protractor at the first corner
while the base edge is drawn (length, or length;angle in the VCB) and a
second one square to the base edge while the width and its angle are set.
IngeTrazo had the geometry of that second step and drew neither."""
from __future__ import annotations

import math

import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QVector3D

from tools.base import ToolContext
from tools.rotated_rectangle import RotatedRectangleTool


def V(x, y, z=0.0):
    return QVector3D(float(x), float(y), float(z))


class _VP:
    """A plan view: 100 px per metre, looking down."""

    def __init__(self):
        self.scene = None
        self.history = None

    def pick_face_any(self, x, y):
        return (None, None)

    def _world_to_pixel(self, p):
        return (p.x() * 100.0, -p.y() * 100.0 - p.z() * 100.0)

    def flash_status(self, *a, **k):
        pass

    def update(self):
        pass


def _ctx(vp, world, mods=Qt.NoModifier):
    px = vp._world_to_pixel(world)
    return ToolContext(viewport=vp, world=world, screen=QPointF(*px),
                       modifiers=mods, snap=None)


def _started(vp):
    tool = RotatedRectangleTool()
    tool.on_click(_ctx(vp, V(0, 0)))
    return tool


def _close(a, b, tol=1e-5):
    return (a - b).length() < tol


def test_the_first_protractor_is_drawn_at_the_first_corner():
    vp = _VP()
    tool = _started(vp)
    tool.on_hover(_ctx(vp, V(3, 1)))
    segs = tool.rubber_band_lines()
    assert len(segs) > 40                     # the edge + rim + ticks
    radii = {round((a - V(0, 0)).length(), 6) for a, _b in segs[1:49]}
    assert radii == {0.6}                     # 60 px at 100 px/m, fixed size
    assert "18°" in tool.value_label()[0]     # the edge's direction, read


def test_near_the_rim_the_edge_turns_in_15_degree_steps():
    vp = _VP()
    tool = _started(vp)
    a = math.radians(37.0)
    tool.on_hover(_ctx(vp, V(0.5 * math.cos(a), 0.5 * math.sin(a))))
    d = tool.hover_point
    assert math.isclose(math.degrees(math.atan2(d.y(), d.x())), 30.0,
                        abs_tol=1e-6)
    assert math.isclose(d.length(), 0.5, abs_tol=1e-6)   # the length stays
    far = V(3 * math.cos(a), 3 * math.sin(a))
    tool.on_hover(_ctx(vp, far))
    assert _close(tool.hover_point, far)                 # far out: free


def test_the_base_edge_can_be_typed_with_its_angle():
    vp = _VP()
    tool = _started(vp)
    tool.on_hover(_ctx(vp, V(1, 0)))
    assert tool.vcb_label == "Length; angle"
    assert tool.on_value(vp, (2.0, 90.0))
    assert _close(tool.base_point, V(0, 2))
    assert tool.vcb_label == "Width; angle"


def test_a_typed_length_follows_the_cursor():
    vp = _VP()
    tool = _started(vp)
    tool.on_hover(_ctx(vp, V(3, 4)))
    assert tool.on_value(vp, 10.0)
    assert _close(tool.base_point, V(6, 8))


def test_the_second_protractor_stands_square_to_the_base_edge():
    vp = _VP()
    tool = _started(vp)
    tool.on_click(_ctx(vp, V(2, 0)))
    tool.on_hover(_ctx(vp, V(1, 1)))
    disc = tool.rubber_band_lines()[4:]
    assert disc
    for a, b in disc:                         # every point in the plane x = 2
        assert abs(a.x() - 2.0) < 1e-6 and abs(b.x() - 2.0) < 1e-6


def test_shift_holds_the_width_angle():
    vp = _VP()
    tool = _started(vp)
    tool.on_click(_ctx(vp, V(2, 0)))
    tool.on_hover(_ctx(vp, V(1, 3)))
    assert tool.angle == 0.0                  # flat on the ground
    tool.on_hover(_ctx(vp, V(1, 3), Qt.ShiftModifier))
    tool.on_hover(_ctx(vp, V(1, 1, 5), Qt.ShiftModifier))   # would stand up
    w, angle = tool._width_and_angle(tool.hover_point, tool._locked)
    assert angle == 0.0 and math.isclose(w, 1.0, abs_tol=1e-6)


def test_an_angle_is_not_a_length_in_a_millimetre_model(monkeypatch):
    """«3;90» in a millimetre document: the parser reads bare fields as
    millimetres, so the angle reached the tool as 0.09."""
    import core.units as units
    monkeypatch.setattr(units, "bare_number_scale", lambda: 0.001)
    vp = _VP()
    tool = _started(vp)
    tool.on_hover(_ctx(vp, V(1, 0)))
    assert tool.on_value(vp, (2.0, 90.0 * 0.001))
    assert _close(tool.base_point, V(0, 2))


class _EyeVP(_VP):
    """A perspective eye: the ray through the pixel runs from ``eye`` to
    ``aim`` (the pixel is irrelevant here, the stub aims for us)."""

    def __init__(self, eye, aim):
        super().__init__()
        self._eye, self._aim = eye, aim

    def _pixel_to_ray(self, x, y):
        return self._eye, (self._aim - self._eye).normalized()


def _ctx_snap(vp, world, kind):
    from core.snap import SnapResult
    return ToolContext(viewport=vp, world=world, screen=QPointF(0, 0),
                       modifiers=Qt.NoModifier, snap=SnapResult(world, kind))


def test_the_width_is_read_on_the_second_protractors_plane():
    """Marco, 2026-09-23: «me fuerza a 180° a no ser que cambie un poco la
    vista». The snap answers on the ground, so the width could only lie
    on it; the cursor is read where its ray meets the protractor."""
    aim = V(2, -1, 1)                          # on the plane x = 2
    vp = _EyeVP(V(5, -4, 3), aim)
    tool = RotatedRectangleTool()
    tool.on_click(_ctx_snap(vp, V(0, 0), "none"))
    tool.on_click(_ctx_snap(vp, V(2, 0), "none"))
    ground = V(2 + 3 * (3 / 2), -1 - 3 * (3 / 2), 0)   # where the ray hits z=0
    tool.on_hover(_ctx_snap(vp, ground, "none"))
    assert _close(tool.hover_point, aim)
    w, angle = tool._width_and_angle(tool.hover_point, None)
    assert math.isclose(angle, 135.0, abs_tol=1e-6)    # tilted, not 180°
    assert math.isclose(w, math.sqrt(2), abs_tol=1e-6)


def test_a_snapped_point_keeps_the_width_on_it():
    vp = _EyeVP(V(5, -4, 3), V(2, -1, 1))
    tool = RotatedRectangleTool()
    tool.on_click(_ctx_snap(vp, V(0, 0), "none"))
    tool.on_click(_ctx_snap(vp, V(2, 0), "none"))
    corner = V(2, 3, 0)
    tool.on_hover(_ctx_snap(vp, corner, "endpoint"))
    assert _close(tool.hover_point, corner)
