"""A door drawn from the floor goes through the wall (Rafael, revision 4).

Pushing a door that starts at the bottom edge of a wall through it turns the
bottom ring into a C. The plane rebuild asked a point "inside" the C and got
one in its notch (the old interior point was a nudge toward the vertex
average), read the C as outside the solid, dropped the whole bottom face,
and the push was refused as breaking the solid — a 0.30 m blind niche where
the door should be. It depended on the order of the faces in the mesh, so
some houses worked and others never did."""
from __future__ import annotations

import io
import contextlib
import random

from PySide6.QtGui import QVector3D as V
from PySide6.QtWidgets import QApplication

from core import solids
from core.arrangement import _interior_point, _point_in_polygon
from core.cap_rebuild import _region_test_point
from core.edits import build_add_edges
from core.history import History
from core.mesh import Mesh
from core.orient import is_closed
from core.scene import Scene
from tests.test_pushpull_ux import _StubViewport
from tests.test_solid_tools import BLUE, RED, _box
from tools.pushpull import PushPullTool

_app = QApplication.instance() or QApplication([])

T = 0.3

# The bottom ring of a 10 m house with 0.30 m walls, once a 1 m door has
# been cut through its front wall: a C whose FIRST edge is the notch side.
C_SHAPE = [(5.0, 0.3), (5.0, 0.0), (10.0, 0.0), (10.0, 10.0), (0.0, 10.0),
           (0.0, 0.0), (4.0, 0.0), (4.0, 0.3), (0.3, 0.3), (0.3, 9.7),
           (9.7, 9.7), (9.7, 0.3)]


def test_the_interior_point_of_a_c_is_inside_it():
    assert _point_in_polygon(_interior_point(C_SHAPE), C_SHAPE)
    assert _point_in_polygon(_region_test_point(C_SHAPE, []), C_SHAPE)


def _tube():
    cutter = _box(T, T, -0.5, 10 - T, 10 - T, 3.5, RED, "A")
    house = _box(0, 0, 0, 10, 10, 3, BLUE, "B")
    return solids.run(solids.SUBTRACT, [cutter, house])[1][0].mesh


def _reordered(mesh, order):
    out = Mesh()
    faces = list(mesh.faces)
    for i in order:
        f = faces[i]
        out.add_face([V(v) for v in f.vertices],
                     [[V(v) for v in h] for h in f.holes] or None)
    return out


def _push_door(mesh):
    scene = Scene()
    hist = History(scene)
    scene.mesh = mesh
    p = [V(4, 0, 0), V(4, 0, 2), V(5, 0, 2), V(5, 0, 0)]
    hist.execute(build_add_edges(scene, [(p[0], p[1]), (p[1], p[2]), (p[2], p[3])]))
    door = min((f for f in scene.mesh.faces
                if all(abs(v.y()) < 1e-6 and 4 - 1e-6 <= v.x() <= 5 + 1e-6
                       and v.z() <= 2 + 1e-6 for v in f.vertices)),
               key=lambda f: f.area())
    vp = _StubViewport(scene)
    tool = PushPullTool()
    tool.base_face, tool.dragging, tool._group = door, True, None
    target = tool._target_scene(scene)
    tool._anchor, tool._normal = door.centroid(), door.normal()
    tool._attached, tool._prism_cap = tool._classify_base(target)
    tool._cap_positions = tool._cap_loop_positions(door)
    tool._compute_inward_limit(target)
    tool.extrusion = -5.0
    with contextlib.redirect_stdout(io.StringIO()):
        tool._clamp_extrusion(vp)
        tool._commit(vp)
    return scene.mesh


def test_a_floor_door_goes_through_a_subtracted_wall_in_any_face_order():
    rng = random.Random(1)
    base = _tube()
    for _ in range(12):
        order = list(range(len(base.faces)))
        rng.shuffle(order)
        mesh = _push_door(_reordered(base, order))
        assert is_closed(mesh)
        bottom = [f for f in mesh.faces
                  if all(abs(v.z()) < 1e-6 for v in f.vertices)]
        # The bottom ring survives as the C around the door opening.
        assert [(len(f.vertices), len(f.holes)) for f in bottom] == [(12, 0)]
