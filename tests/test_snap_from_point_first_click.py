# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""'From point' before the first click (Rafael's review, 2026-09-10, B4).

He hovered the door's top corner with the Rectangle tool and moved right
along the wall to start the window level with it — «te salía una línea de
extensión para poder dibujar aquí la ventana… como que quiere, pero no sale».
SketchUp's encouraged-point inference: the last hovered corner stays acquired
and the cursor lines up with it along an axis on a dotted line. Ours only knew
the from-point while a segment was under way.
"""
from __future__ import annotations

import math

from PySide6.QtGui import QVector3D

from core.scene import Scene
from core.snap import AXIS_COLORS, compute_snap


def V(x, y, z=0.0):
    return QVector3D(float(x), float(y), float(z))


def _w2p(p):                      # an elevation: x → right, z → up
    return (p.x() * 100.0, -p.z() * 100.0)


def _snap(scene, cand, **kw):
    return compute_snap(cand, _w2p(cand), scene, _w2p,
                        threshold_px=9.0, edge_threshold_px=14.0, **kw)


def _wall_with_door():
    scene = Scene()
    scene.mesh.add_edge(V(1, 0, 0), V(1, 0, 2))     # door jambs and lintel
    scene.mesh.add_edge(V(2, 0, 0), V(2, 0, 2))
    scene.mesh.add_edge(V(1, 0, 2), V(2, 0, 2))
    return scene


def test_the_first_corner_lines_up_with_the_hovered_corner_along_an_axis():
    scene = _wall_with_door()
    r = _snap(scene, V(3.5, 0, 2.03), acquired_point=V(2, 0, 2))   # level with the lintel
    assert r.kind == "from_point"
    assert abs(r.point.z() - 2.0) < 1e-9 and abs(r.point.x() - 3.5) < 1e-9
    assert r.guide is not None and (r.guide[0] - V(2, 0, 2)).length() < 1e-9
    assert r.guide_color == AXIS_COLORS["x"]                        # red dotted line


def test_it_stays_quiet_off_the_axis_lines_and_without_a_corner():
    scene = _wall_with_door()
    assert _snap(scene, V(3.5, 0, 2.5), acquired_point=V(2, 0, 2)).kind != "from_point"
    assert _snap(scene, V(3.5, 0, 2.03)).kind != "from_point"


def test_the_corner_itself_is_still_an_endpoint():
    scene = _wall_with_door()
    r = _snap(scene, V(2.01, 0, 2.01), acquired_point=V(2, 0, 2))
    assert r.kind == "endpoint"


def test_the_viewport_keeps_the_hovered_corner_before_the_first_click():
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    import pytest
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    elif not isinstance(app, QApplication):
        pytest.skip("another Qt application flavour is already running")
    from views.viewport import Viewport
    from tools.rectangle import RectangleTool
    vp = Viewport(None)
    vp.resize(1000, 600)
    vp.camera.set_aspect(1000, 600)
    vp.flash_status = lambda *a, **k: None
    vp.scene.mesh.add_face([V(0, 0, 0), V(4, 0, 0), V(4, 0, 3), V(0, 0, 3)])
    vp.scene.version += 1
    vp.camera.set_view("front")
    vp.camera.target = V(2, 0, 1.5)
    vp.camera.distance = 12
    vp.set_active_tool(RectangleTool())
    corner_px = vp._world_to_pixel(V(4, 0, 3))
    vp._process_hover(QPointF(*corner_px), Qt.NoModifier)
    assert vp._acquired_point is None                  # crossing it is not enough
    assert vp._dwell_timer.isActive()
    vp._encourage_dwelt()                              # …pausing on it is (the timer)
    assert vp._acquired_point is not None and (vp._acquired_point - V(4, 0, 3)).length() < 1e-6
    away_px = vp._world_to_pixel(V(2, 0, 1))
    vp._process_hover(QPointF(*away_px), Qt.NoModifier)
    assert (vp._acquired_point - V(4, 0, 3)).length() < 1e-6      # still encouraged


def test_hovering_a_circles_rim_encourages_its_centre(monkeypatch):
    """Marco's capture of SketchUp (2026-09-14): with the Circle tool on
    another circle's rim, the dotted line runs from THAT circle's centre —
    the centre is an encouraged point like a corner."""
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    import pytest
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    elif not isinstance(app, QApplication):
        pytest.skip("another Qt application flavour is already running")
    from views.viewport import Viewport
    from tools.circle import CircleTool
    from tools.base import ToolContext
    vp = Viewport(None)
    vp.resize(1000, 600)
    vp.camera.set_aspect(1000, 600)
    vp.flash_status = lambda *a, **k: None
    vp.camera.set_view("top")
    vp.camera.target = V(3, 2, 0)
    vp.camera.distance = 12
    tool = CircleTool()
    vp.set_active_tool(tool)

    def ctx(world):
        return ToolContext(viewport=vp, world=world, screen=QPointF(0, 0),
                           modifiers=Qt.NoModifier, snap=None)
    tool.on_click(ctx(V(2, 2, 0)))
    tool.on_click(ctx(V(3, 2, 0)))                  # a circle, centre (2,2), r = 1
    assert len(vp.scene.mesh.edges) >= 12
    tool2 = CircleTool()
    vp.set_active_tool(tool2)
    # The rim between two of its vertices (a vertex under the cursor would
    # rightly be the encouraged point instead).
    a0, a1 = 0.0, 2 * math.pi / tool.sides
    mid = V(2 + (math.cos(a0) + math.cos(a1)) / 2, 2 + (math.sin(a0) + math.sin(a1)) / 2, 0)
    rim_px = vp._world_to_pixel(mid)
    vp._process_hover(QPointF(*rim_px), Qt.NoModifier)   # hover the rim…
    vp._encourage_dwelt()                                # …and pause on it
    assert vp._acquired_point is not None
    assert (vp._acquired_point - V(2, 2, 0)).length() < 1e-3
    far_px = vp._world_to_pixel(V(5, 2.02, 0))          # level with the centre, along red
    vp._process_hover(QPointF(*far_px), Qt.NoModifier)
    snap = vp.last_snap
    assert snap.kind == "from_point", snap.kind
    assert abs(snap.point.y() - 2.0) < 1e-6 and abs(snap.point.x() - 5.0) < 0.05
    assert (snap.guide[0] - V(2, 2, 0)).length() < 1e-3


# ---------------------------------------------------------------------------
# The rest of SketchUp's inference catalogue (Marco, 2026-09-14: «haz todas»).

def test_two_encouraged_points_pin_the_cursor_where_their_axis_lines_cross():
    """MasterSketchUp's two-point method: hover one corner, then another,
    and the cursor snaps where the dotted line from each crosses — level
    with the lintel AND in line with the far jamb."""
    scene = _wall_with_door()
    lintel_end, jamb_foot = V(2, 0, 2), V(5, 0, 0)
    r = _snap(scene, V(4.97, 0, 2.04), acquired_points=[lintel_end, jamb_foot],
              acquired_point=jamb_foot)
    assert r.kind == "from_point"
    assert abs(r.point.x() - 5.0) < 1e-9 and abs(r.point.z() - 2.0) < 1e-9
    assert r.guides and len(r.guides) == 1                  # a second dotted guide
    starts = {tuple(round(c, 6) for c in (g.x(), g.y(), g.z()))
              for g in (r.guide[0], r.guides[0][0])}
    assert starts == {(2.0, 0.0, 2.0), (5.0, 0.0, 0.0)}
    colours = {r.guide_color, r.guides[0][2]}
    assert colours == {AXIS_COLORS["x"], AXIS_COLORS["z"]}


def test_the_viewport_keeps_the_last_two_encouraged_points():
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from views.viewport import Viewport
    vp = Viewport(None)
    for pt in (V(1, 0, 0), V(2, 0, 0), V(3, 0, 0), V(3, 0, 0)):
        vp.encourage_point(pt)
    assert [p.x() for p in vp._encouraged] == [2.0, 3.0]
    assert vp._acquired_point.x() == 3.0


def test_guides_read_on_line_and_group_points_are_magenta():
    from types import SimpleNamespace
    from views.viewport import _SnapEdge
    from core.snap import COLOR_IN_GROUP, COLOR_ON_EDGE
    scene = SimpleNamespace(edges=[                           # (an elevation: x, z)
        _SnapEdge(V(0, 0, 0), V(4, 0, 0), guide=True),          # a guide line
        _SnapEdge(V(0, 0, 2), V(4, 0, 2), in_group=True),       # a group's edge
    ])
    r = _snap(scene, V(2, 0, 0.02))
    assert r.kind == "on_line" and r.color == COLOR_ON_EDGE
    assert _snap(scene, V(4.0, 0, 0.01)).kind != "endpoint"     # a guide has no ends
    r = _snap(scene, V(4.01, 0, 2.01))
    assert r.kind == "endpoint" and r.color == COLOR_IN_GROUP
    r = _snap(scene, V(2.0, 0, 2.02))
    assert r.kind == "midpoint" and r.color == COLOR_IN_GROUP


def test_component_origin_and_arc_midpoint_pseudo_edges_snap_by_name():
    from types import SimpleNamespace
    from views.viewport import _SnapEdge
    scene = SimpleNamespace(edges=[
        _SnapEdge(V(1, 1, 0), V(1, 1, 0), component_origin=True),
        _SnapEdge(V(3, 3, 0), V(3, 3, 0), arc_midpoint=True),
    ])
    assert _snap(scene, V(1.02, 1.0, 0)).kind == "component_origin"
    assert _snap(scene, V(3.0, 3.02, 0)).kind == "arc_midpoint"


def test_the_viewport_offers_an_arcs_sweep_midpoint_and_a_groups_origin():
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtGui import QMatrix4x4
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from views.viewport import Viewport
    from tools.arc import ArcTool
    from tools.line import LineTool
    from tools.base import ToolContext
    from core.group import Group
    from core.mesh import Mesh
    vp = Viewport(None)
    vp.resize(1000, 600)
    vp.camera.set_aspect(1000, 600)
    vp.flash_status = lambda *a, **k: None
    vp.camera.set_view("top")
    vp.camera.target = V(3, 2, 0)
    vp.camera.distance = 12
    arc = ArcTool()
    vp.set_active_tool(arc)

    def ctx(world):
        return ToolContext(viewport=vp, world=world, screen=QPointF(0, 0),
                           modifiers=Qt.NoModifier, snap=None)
    arc.on_click(ctx(V(0, 0, 0)))
    arc.on_click(ctx(V(2, 0, 0)))
    arc.on_click(ctx(V(1, 1, 0)))                      # a half circle, r = 1
    mesh = Mesh()
    mesh.add_face([V(0, 0, 0), V(1, 0, 0), V(1, 1, 0), V(0, 1, 0)])
    g = Group(mesh, "caja")
    xf = QMatrix4x4()
    xf.translate(5, 4, 0)
    g.xform = xf
    vp.scene.groups.append(g)
    vp.scene.version += 1
    vp.set_active_tool(LineTool())
    px = vp._world_to_pixel(V(1, 1.02, 0))               # the arc's apex
    vp._process_hover(QPointF(*px), Qt.NoModifier)
    assert vp.last_snap.kind == "arc_midpoint", vp.last_snap.kind
    assert (vp.last_snap.point - V(1, 1, 0)).length() < 0.02
    px = vp._world_to_pixel(V(5.02, 4.0, 0))             # the group's origin
    vp._process_hover(QPointF(*px), Qt.NoModifier)
    assert vp.last_snap.kind == "component_origin", vp.last_snap.kind


def test_an_arc_started_at_another_arcs_end_snaps_tangent_to_it():
    """SketchUp's "Tangent at Vertex" (cyan): an arc that starts at the end
    of another arc snaps its bulge so the two run tangent — an S-curve here:
    the half circle over (0..2) continues below (2..4) with the same radius."""
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from views.viewport import Viewport
    from tools.arc import ArcTool
    from tools.base import ToolContext
    from core.snap import COLOR_TANGENT
    vp = Viewport(None)
    vp.resize(1000, 600)
    vp.camera.set_aspect(1000, 600)
    vp.flash_status = lambda *a, **k: None
    vp.camera.set_view("top")
    vp.camera.target = V(2, 0, 0)
    vp.camera.distance = 12

    def ctx(world):
        return ToolContext(viewport=vp, world=world, screen=QPointF(0, 0),
                           modifiers=Qt.NoModifier, snap=None)
    first = ArcTool()
    vp.set_active_tool(first)
    first.on_click(ctx(V(0, 0, 0)))
    first.on_click(ctx(V(2, 0, 0)))
    first.on_click(ctx(V(1, 1, 0)))                    # half circle, centre (1,0), r = 1
    arc = ArcTool()
    vp.set_active_tool(arc)
    arc.on_click(ctx(V(2, 0, 0)))                      # start at the other arc's end
    arc.on_click(ctx(V(4, 0, 0)))
    assert arc._tangent_dir is not None
    assert (arc._tangent_dir - V(0, -1, 0)).length() < 1e-6   # leaving downward
    arc.on_hover(ctx(V(3, -0.9, 0)))                   # near the tangent bulge (-1)
    assert arc._snap_bulge is not None and abs(arc._snap_bulge + 1.0) < 1e-6
    assert arc.wireframe_color[:3] == COLOR_TANGENT
    apex = min(arc._points(arc.hover_point), key=lambda p: p.y())
    assert (apex - V(3, -1, 0)).length() < 1e-3
    assert "Tangent" in arc.value_label()[0]
    arc.on_hover(ctx(V(3, -0.5, 0)))                   # too far from tangent: free bulge
    assert arc._snap_bulge is None and arc.wireframe_color is None
