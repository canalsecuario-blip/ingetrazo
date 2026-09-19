# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""The automatic orientation pass must not move paint to the other side.

Marco, 2026-09-18, on seeing a blue face turn white after a push: «¿qué
pasa si tengo una casa con paredes, texturas exteriores diferentes a las
interiores, hago push de adentro? ¿La textura cambiaría?»

It would have. ``orient_outward`` fixed a wrong winding by reversing the
loop, and paint lives by side — the front's in ``attrs``, the back's own in
``attrs["back"]`` — so the front's plaster went to the street and the
brick came indoors. Now a face painted on BOTH sides keeps each paint on
the side it was; only the winding turns. A face painted on one side keeps
following the correction (a painted rectangle pulled into a box must come
out painted underneath too).
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QGuiApplication, QVector3D

_app = QGuiApplication.instance() or QGuiApplication([])

from core.history import FlipFacesCommand, History
from core.mesh import Mesh, turn_face_over
from core.orient import orient_outward
from core.scene import Scene

BRICK = {"color": [0.7, 0.3, 0.2], "mat": "Ladrillo"}
PLASTER = {"color": [0.95, 0.95, 0.9], "mat": "Yeso"}


def _cube(mesh, inverted_face="south"):
    """A unit cube, every face outward except one wound the wrong way."""
    P = [QVector3D(x, y, z) for z in (0, 1) for y in (0, 1) for x in (0, 1)]
    quads = {
        "bottom": [P[0], P[2], P[3], P[1]], "top": [P[4], P[5], P[7], P[6]],
        "south": [P[0], P[1], P[5], P[4]], "north": [P[2], P[6], P[7], P[3]],
        "west": [P[0], P[4], P[6], P[2]], "east": [P[1], P[3], P[7], P[5]],
    }
    faces = {}
    for name, loop in quads.items():
        if name == inverted_face:
            loop = loop[::-1]
        faces[name] = mesh.add_face(loop)
    return faces


def test_orient_outward_swaps_the_paints_with_the_winding():
    mesh = Mesh()
    faces = _cube(mesh)
    south = faces["south"]
    assert south.normal().y() > 0.99          # wound inward: normal into the cube
    # Painted the way a user would: clicking from OUTSIDE hits the geometric
    # outside, which on this inverted face is its BACK → brick goes there.
    south.attrs.update(PLASTER)               # the front, facing the room
    south.attrs["back"] = dict(BRICK)         # the back, facing the street
    flipped = orient_outward(mesh)
    assert south in flipped and south.normal().y() < -0.99
    # The street side still shows brick, the room side still plaster.
    assert {k: south.attrs[k] for k in BRICK} == BRICK
    assert south.attrs["back"] == PLASTER


def test_paint_on_the_back_alone_moves_to_the_front_with_the_turn():
    """Clicking the outside of an inverted face paints its BACK; the turn
    makes that side the front, and the brick stays where it was seen."""
    mesh = Mesh()
    south = _cube(mesh)["south"]
    south.attrs["back"] = dict(BRICK)         # only the street side painted
    orient_outward(mesh)
    assert {k: south.attrs[k] for k in BRICK} == BRICK
    assert "back" not in south.attrs          # the room side: default again


def test_paint_on_the_front_alone_follows_the_correction():
    """The old rule, kept on purpose: a painted rectangle pulled into a box
    has its base turned over, and the paint must come out OUTSIDE («a
    painted box, not a box with one painted face», Marco, 2026-08-27)."""
    mesh = Mesh()
    south = _cube(mesh)["south"]
    south.attrs.update(PLASTER)
    orient_outward(mesh)
    assert south.normal().y() < -0.99
    assert {k: south.attrs[k] for k in PLASTER} == PLASTER
    assert "back" not in south.attrs


def test_a_mirrored_two_sided_face_is_left_alone():
    mesh = Mesh()
    south = _cube(mesh)["south"]
    south.attrs.update(BRICK)
    south.attrs["back"] = True                # both sides the same
    orient_outward(mesh)
    assert south.normal().y() < -0.99
    assert {k: south.attrs[k] for k in BRICK} == BRICK
    assert south.attrs["back"] is True


def test_turn_face_over_is_an_involution():
    mesh = Mesh()
    south = _cube(mesh)["south"]
    south.attrs.update(PLASTER)
    south.attrs["back"] = dict(BRICK)
    before = dict(south.attrs), list(south.loop)
    turn_face_over(south)
    turn_face_over(south)
    assert (dict(south.attrs), list(south.loop)) == before


def test_reverse_faces_keeps_sketchups_meaning():
    """The user's Reverse Faces is SketchUp's: the material follows the
    front, so it moves to the other side. Only the automatic pass differs."""
    scene = Scene()
    south = _cube(scene.mesh)["south"]
    south.attrs.update(PLASTER)
    south.attrs["back"] = dict(BRICK)
    History(scene).execute(FlipFacesCommand([south]))
    assert south.normal().y() < -0.99
    assert {k: south.attrs[k] for k in PLASTER} == PLASTER
    assert south.attrs["back"] == BRICK


def test_pushing_an_inverted_wall_from_inside_keeps_the_brick_outside():
    """The whole road: a wall wound the wrong way, brick outside and plaster
    inside, pushed from inside the room — the drag's orientation pass turns
    it over, and the street keeps its brick."""
    from tools.base import ToolContext
    from tools.pushpull import PushPullTool

    class _Vp:
        def __init__(self, scene):
            self.scene = scene
            self.history = History(scene)

        def set_hover(self, *_):
            pass

        def set_suppressed_faces(self, *_):
            pass

        def update(self):
            pass

        def flash_status(self, *_):
            pass

    scene = Scene()
    south = _cube(scene.mesh)["south"]
    south.attrs.update(PLASTER)
    south.attrs["back"] = dict(BRICK)
    vp = _Vp(scene)
    pp = PushPullTool()
    pp.hovered_face = south
    pp._hover_group = None
    pp.on_click(ToolContext(viewport=vp, world=QVector3D(0, 0, 0),
                            screen=QPointF(400, 300),
                            modifiers=Qt.NoModifier, snap=None))
    pp.extrusion = 0.3                        # a bump out toward the street
    pp._commit(vp)
    street = [f for f in scene.mesh.faces
              if all(abs(v.position.y() + 0.3) < 1e-6 for v in f.loop)]
    assert len(street) == 1
    cap = street[0]
    assert cap.normal().y() < -0.99
    assert {k: cap.attrs[k] for k in BRICK} == BRICK
    assert cap.attrs["back"] == PLASTER
