# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""Issue #44 (@pacaeiro), phase 2: inside a group you draw on ITS axes.

SketchUp: «when you open a group for editing you see its axes, not the
model axes» — the red/green/blue inferences, the arrow-key locks, the
rectangle and the ground follow them, level by level. ``core.axes`` holds
the one table every tool reads; the viewport syncs it to the open
context."""
from __future__ import annotations

import math
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPointF  # noqa: E402
from PySide6.QtGui import QMatrix4x4, QVector3D  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

if QApplication.instance() is None:
    QApplication([])

from core import axes  # noqa: E402
from core.group import Group, frame_axes, group_frame  # noqa: E402
from core.history import MakeGroupCommand  # noqa: E402
from core.mesh import Mesh  # noqa: E402
from core.scene import Scene  # noqa: E402


def V(x, y, z=0.0):
    return QVector3D(float(x), float(y), float(z))


def _close(a, b, tol=1e-4):
    return (a - b).length() < tol


def _turn(deg=30.0):
    m = QMatrix4x4()
    m.translate(2, 1, 0)
    m.rotate(deg, 0, 0, 1)
    return m


def test_the_world_frame_is_bit_for_bit_the_old_tables():
    from core.snap import _AXIS_VECTORS
    from tools.base import PLANE_LOCK_AXES
    assert _AXIS_VECTORS is axes.AXES and PLANE_LOCK_AXES is axes.AXES
    assert [tuple((v.x(), v.y(), v.z())) for v in axes.AXES.values()] == [
        (1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)]
    assert axes.is_world()


def test_sync_turns_every_table_at_once_and_back():
    from core.snap import _AXIS_VECTORS
    axes.sync(_turn())
    a = math.radians(30)
    assert _close(_AXIS_VECTORS["x"], V(math.cos(a), math.sin(a)))
    assert _close(axes.ORIGIN, V(2, 1))
    axes.sync(None)
    assert _AXIS_VECTORS["x"] == V(1, 0, 0) and axes.ORIGIN == V(0, 0, 0)


def test_axis_alignment_is_measured_on_the_local_axes():
    from core.snap import _detect_axis_alignment
    a = math.radians(30)
    along_red = V(math.cos(a), math.sin(a))
    assert _detect_axis_alignment(V(0, 0), along_red, 3.0) is None  # world
    axes.sync(_turn())
    assert _detect_axis_alignment(V(0, 0), along_red, 3.0) == "x"


def test_plane_lock_and_default_ground_follow_the_context():
    from tools.rectangle import RectangleTool
    frame = QMatrix4x4()
    frame.rotate(90.0, 1, 0, 0)                 # the group stands up
    axes.sync(frame)
    tool = RectangleTool()
    tool.plane_lock = "z"
    _p, n = tool.locked_work_plane(V(0, 0))
    assert _close(n, V(0, -1, 0)) or _close(n, V(0, 1, 0))   # local blue
    tool.plane_lock = None
    tool.work_plane = None
    tool.hover_plane = None
    _o, ground = tool.drawing_plane()
    assert _close(ground, axes.axis("z"))


def test_a_rectangle_lines_up_with_the_group():
    from core.axes import plane_axes
    axes.sync(_turn(30.0))
    u, v = plane_axes(V(0, 0, 1))
    a = math.radians(30)
    assert _close(u, V(math.cos(a), math.sin(a)))


# ---- Through the real viewport ------------------------------------------------

def _vp_in_turned_group():
    from views.viewport import Viewport
    vp = Viewport(None)
    vp.resize(1000, 700)
    vp.camera.set_aspect(1000, 700)
    vp.flash_status = lambda *a, **k: None
    m = Mesh()
    m.add_face([V(-1, -1), V(1, -1), V(1, 1), V(-1, 1)])
    g = Group(m, name="turned")
    g.axes = _turn(30.0)
    vp.scene.groups.append(g)
    vp.scene.version += 1
    vp.begin_group_edit(g)
    vp.camera.set_view("top")
    vp.camera.target = V(2, 1)
    vp.camera.distance = 12
    return vp, g


def test_the_viewport_syncs_the_axes_as_it_enters_and_leaves():
    vp, _g = _vp_in_turned_group()
    vp._sync_axes()
    assert not axes.is_world()
    vp.end_group_edit()
    vp._sync_axes()
    assert axes.is_world()


def test_an_arrow_lock_inside_the_group_runs_along_its_red():
    from tools.line import LineTool
    vp, _g = _vp_in_turned_group()
    tool = LineTool()
    vp.active_tool = tool
    tool.start_point = V(2, 1)
    vp.axis_lock = "x"
    px, py = vp._world_to_pixel(V(3.5, 3.0))       # well off the red
    vp._last_mouse_pos = QPointF(px, py)
    vp._refresh_snap()
    s = vp.last_snap
    d = s.point - V(2, 1)
    a = math.radians(30)
    red = V(math.cos(a), math.sin(a))
    assert d.length() > 0.1
    assert _close(d.normalized(), red) or _close(d.normalized(), -red)


def test_the_axes_are_drawn_at_the_groups_origin():
    from views.viewport import _axes_vertices
    vp, _g = _vp_in_turned_group()
    vp._sync_axes()
    coords, spans = _axes_vertices(0.1)
    start, _n = spans["x"]
    o = V(coords[start * 3], coords[start * 3 + 1], coords[start * 3 + 2])
    tip = V(coords[start * 3 + 3], coords[start * 3 + 4], coords[start * 3 + 5])
    assert _close(o, V(2, 1))
    a = math.radians(30)
    assert _close((tip - o).normalized(), V(math.cos(a), math.sin(a)))


def test_a_group_made_inside_takes_the_contexts_axes():
    scene = Scene()
    outer = Group(Mesh(), name="outer")
    outer.axes = _turn(30.0)
    scene.groups.append(outer)
    scene.begin_group_edit(outer)
    f = scene.mesh.add_face([V(2, 1), V(3, 1), V(3, 2), V(2, 2)])
    cmd = MakeGroupCommand([f], [])
    cmd.do(scene)
    _o, x, _y, _z = frame_axes(group_frame(cmd.group))
    a = math.radians(30)
    assert _close(x, V(math.cos(a), math.sin(a)))


def test_a_component_made_inside_is_placed_on_the_contexts_axes():
    scene = Scene()
    outer = Group(Mesh(), name="outer")
    outer.axes = _turn(30.0)
    scene.groups.append(outer)
    scene.begin_group_edit(outer)
    pts = [V(2, 1), V(3, 1), V(3, 2), V(2, 2)]
    f = scene.mesh.add_face(pts)
    cmd = MakeGroupCommand([f], [], component=True)
    cmd.do(scene)
    g = cmd.group
    _o, x, _y, _z = frame_axes(group_frame(g))
    a = math.radians(30)
    assert _close(x, V(math.cos(a), math.sin(a)))
    # the geometry did not move in the world
    from core.group import world_mesh
    got = sorted((round(v.position.x(), 4), round(v.position.y(), 4))
                 for v in world_mesh(g).vertices)
    assert got == sorted((round(p.x(), 4), round(p.y(), 4)) for p in pts)
