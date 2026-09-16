# SPDX-License-Identifier: GPL-3.0-or-later
"""Arrow keys before the first click lock a planar tool's drawing plane
(SketchUp; Marco, 2026-09-08: «quiero dibujar un círculo en el plano ZX…
me restringe a qué plano quiero dibujar apretando las teclas de
desplazamiento»)."""
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QVector3D

from core.history import History
from core.scene import Scene
from tools.arc import CenterArcTool
from tools.base import ToolContext
from tools.circle import CircleTool, PolygonTool
from tools.rectangle import RectangleTool


def V(x, y, z=0.0):
    return QVector3D(float(x), float(y), float(z))


class _Stub:
    def __init__(self):
        self.scene = Scene()
        self.history = History(self.scene)
        self.flashed = []

    def update(self):
        pass

    def flash_status(self, text, msec=2500):
        self.flashed.append(text)


def _ctx(vp, p):
    return ToolContext(viewport=vp, world=p, screen=QPointF(),
                       modifiers=Qt.NoModifier, snap=None)


def test_left_arrow_locks_a_circle_to_the_xz_plane_and_the_shape_spends_it():
    vp = _Stub()
    tool = CircleTool()
    tool.on_activate(vp)
    assert tool.on_key(vp, int(Qt.Key_Left), Qt.NoModifier)
    assert tool.plane_lock == "y" and "XZ" in vp.flashed[-1]
    tool.on_click(_ctx(vp, V(1, 2, 3)))                 # the centre
    assert tool.work_plane[1] == V(0, 1, 0)
    # after the first click the arrows are not the tool's business
    assert not tool.on_key(vp, int(Qt.Key_Up), Qt.NoModifier)
    tool.on_click(_ctx(vp, V(2.5, 2, 3)))               # the rim
    faces = vp.scene.mesh.faces
    assert len(faces) == 1
    assert all(abs(v.y() - 2.0) < 1e-9 for v in faces[0].vertices)
    assert {round(v.z(), 6) for v in faces[0].vertices} != {3.0}
    assert tool.plane_lock is None and tool.work_plane is None   # spent


def test_same_arrow_again_frees_and_right_up_pick_the_other_planes():
    vp = _Stub()
    tool = PolygonTool()
    tool.on_activate(vp)
    tool.on_key(vp, int(Qt.Key_Right), Qt.NoModifier)
    assert tool.plane_lock == "x"
    tool.on_key(vp, int(Qt.Key_Right), Qt.NoModifier)
    assert tool.plane_lock is None and "free" in vp.flashed[-1].lower() \
        or "libre" in vp.flashed[-1].lower()
    tool.on_key(vp, int(Qt.Key_Up), Qt.NoModifier)
    assert tool.plane_lock == "z"
    assert tool.on_key(vp, int(Qt.Key_Down), Qt.NoModifier)   # Down is ours too
    assert tool.plane_lock == "z"                          # (nothing hovered: no-op)
    tool.on_cancel(vp)
    assert tool.plane_lock is None                       # Esc releases it


def test_rectangle_and_centre_arc_lock_too():
    vp = _Stub()
    rect = RectangleTool()
    rect.on_activate(vp)
    rect.on_key(vp, int(Qt.Key_Right), Qt.NoModifier)   # normal X → YZ
    rect.on_click(_ctx(vp, V(0, 0, 0)))
    rect.on_click(_ctx(vp, V(0, 3, 2)))
    face = vp.scene.mesh.faces[-1]
    assert all(abs(v.x()) < 1e-9 for v in face.vertices)
    assert len({round(v.z(), 6) for v in face.vertices}) == 2
    arc = CenterArcTool()
    arc.on_activate(vp)
    arc.on_key(vp, int(Qt.Key_Left), Qt.NoModifier)
    arc.on_click(_ctx(vp, V(5, 5, 5)))
    assert arc.work_plane == (V(5, 5, 5), V(0, 1, 0))


# ---- Down arrow: SketchUp's magenta reference lock (issue #10) -------------

class _Edge:
    def __init__(self, a, b):
        self.a, self.b = a, b


def _perp_to(n, c, verts, tol=1e-6):
    return all(abs(QVector3D.dotProduct(v - c, n)) < tol for v in verts)


def test_down_over_an_inclined_edge_draws_the_circle_perpendicular_to_it():
    """@pacaeiro's pipes: the axis line is inclined (50–55°), the circle must
    be normal to it for Follow Me — Down over the axis line, centre on its
    end, radius. No rotating afterwards."""
    vp = _Stub()
    tool = CircleTool()
    tool.on_activate(vp)
    vp._hover_edge = _Edge(V(0, 0, 0), V(3, 0, 4))      # a 53° axis line
    assert tool.on_key(vp, int(Qt.Key_Down), Qt.NoModifier)
    n, kind = tool.plane_ref
    assert kind == "edge" and abs(n.x() - 0.6) < 1e-6 and abs(n.z() - 0.8) < 1e-6
    assert "perpendicular" in vp.flashed[-1].lower()
    assert tool.lock_color() == (0.85, 0.30, 0.80, 1.0)  # magenta, not an axis
    tool.on_click(_ctx(vp, V(3, 0, 4)))                 # centre on the line's end
    assert tool.work_plane[1] == n
    tool.on_click(_ctx(vp, V(3, 1, 4)))                 # the rim (Y is in-plane)
    faces = vp.scene.mesh.faces
    assert len(faces) == 1
    assert _perp_to(n, V(3, 0, 4), faces[0].vertices)
    assert abs(max((v - V(3, 0, 4)).length() for v in faces[0].vertices) - 1.0) < 1e-6
    assert tool.plane_ref is None and tool.work_plane is None   # spent


def test_down_again_frees_and_an_arrow_replaces_the_reference():
    vp = _Stub()
    tool = PolygonTool()
    tool.on_activate(vp)
    assert tool.on_key(vp, int(Qt.Key_Down), Qt.NoModifier)  # nothing hovered:
    assert tool.plane_ref is None and not vp.flashed         # ours, but no-op
    vp._hover_edge = _Edge(V(0, 0, 0), V(0, 2, 0))
    tool.on_key(vp, int(Qt.Key_Down), Qt.NoModifier)
    assert tool.plane_ref[0] == V(0, 1, 0)
    tool.on_key(vp, int(Qt.Key_Down), Qt.NoModifier)
    assert tool.plane_ref is None
    assert "free" in vp.flashed[-1].lower() or "libre" in vp.flashed[-1].lower()
    tool.on_key(vp, int(Qt.Key_Down), Qt.NoModifier)
    tool.on_key(vp, int(Qt.Key_Up), Qt.NoModifier)           # an axis wins
    assert tool.plane_ref is None and tool.plane_lock == "z"
    tool.on_key(vp, int(Qt.Key_Down), Qt.NoModifier)         # and vice versa
    assert tool.plane_lock is None and tool.plane_ref[1] == "edge"
    tool.on_cancel(vp)
    assert tool.plane_ref is None                            # Esc releases it


def test_down_over_a_face_locks_its_plane_and_the_edge_beats_the_face():
    vp = _Stub()
    rect = RectangleTool()
    rect.on_activate(vp)
    rect.on_key(vp, int(Qt.Key_Right), Qt.NoModifier)        # a YZ wall
    rect.on_click(_ctx(vp, V(0, 0, 0)))
    rect.on_click(_ctx(vp, V(0, 3, 2)))
    wall = vp.scene.mesh.faces[-1]
    vp._last_mouse_pos = QPointF(10, 10)
    vp.pick_face_placement = lambda x, y: (wall, None)
    tool = CircleTool()
    tool.on_activate(vp)
    tool.on_key(vp, int(Qt.Key_Down), Qt.NoModifier)
    n, kind = tool.plane_ref
    assert kind == "face" and abs(abs(n.x()) - 1.0) < 1e-9
    assert "parallel" in vp.flashed[-1].lower() or "paralelo" in vp.flashed[-1].lower()
    tool.on_click(_ctx(vp, V(5, 5, 5)))                      # off the wall, same plane
    assert abs(abs(tool.work_plane[1].x()) - 1.0) < 1e-9
    tool.on_cancel(vp)
    vp._hover_edge = _Edge(V(0, 0, 0), V(0, 0, 1))           # an edge under the cursor too
    tool.on_key(vp, int(Qt.Key_Down), Qt.NoModifier)
    assert tool.plane_ref[1] == "edge" and tool.plane_ref[0] == V(0, 0, 1)
