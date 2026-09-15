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
    vp._process_hover(QPointF(*rim_px), Qt.NoModifier)   # hover the rim
    assert vp._acquired_point is not None
    assert (vp._acquired_point - V(2, 2, 0)).length() < 1e-3
    far_px = vp._world_to_pixel(V(5, 2.02, 0))          # level with the centre, along red
    vp._process_hover(QPointF(*far_px), Qt.NoModifier)
    snap = vp.last_snap
    assert snap.kind == "from_point", snap.kind
    assert abs(snap.point.y() - 2.0) < 1e-6 and abs(snap.point.x() - 5.0) < 0.05
    assert (snap.guide[0] - V(2, 2, 0)).length() < 1e-3
