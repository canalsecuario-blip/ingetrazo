# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""Pushing INTO a face whose back side faces the camera showed no preview.

Marco, 2026-09-18: «el push pull como que no se ve cuando hago push para
adentro cuando tengo la cara invertida… solo no se ve cuando arrastro el
mouse en tiempo real, pero sí hace push».

The drag preview hides the base face so the pocket forming behind it can
be seen. It decided "behind" by the SIGN of the extrusion along the face's
normal — right when the normal points at the viewer, wrong when the viewer
looks at the face's back: the push moves away from the eye, the sign says
"outward", the base stays, and the sweep is buried behind it. The commit
never depended on that, so the push itself worked.

What the renderer needs is the CAMERA's answer: the base must go whenever
the sweep moves away from the eye, whichever way the face is wound.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QGuiApplication, QVector3D

_app = QGuiApplication.instance() or QGuiApplication([])

from core.scene import Scene
from core.history import History
from tools.base import ToolContext
from tools.pushpull import PushPullTool


class _Camera:
    def __init__(self, eye):
        self._eye = QVector3D(eye)

    def eye(self):
        return QVector3D(self._eye)


class _Vp:
    def __init__(self, scene, eye):
        self.scene = scene
        self.history = History(scene)
        self.camera = _Camera(eye)
        self.suppressed = set()

    def set_hover(self, *_):
        pass

    def set_suppressed_faces(self, faces):
        self.suppressed = set(faces)

    def update(self):
        pass

    def flash_status(self, *_):
        pass


def _wall_with_door(scene):
    """A wall panel in the XZ plane at y=0 with a door drawn on it — both
    wound so their normal is +Y. The door is ATTACHED (every edge shared
    with the panel), which is what makes an inward push a recess."""
    mesh = scene.mesh
    outer = [QVector3D(0, 0, 0), QVector3D(0, 0, 3), QVector3D(6, 0, 3),
             QVector3D(6, 0, 0)]
    door = [QVector3D(2, 0, 0), QVector3D(2, 0, 2), QVector3D(3, 0, 2),
            QVector3D(3, 0, 0)]
    panel = mesh.add_face(outer, hole_loops=[list(reversed(door))])
    d = mesh.add_face(door)
    assert panel.normal().y() > 0.99 and d.normal().y() > 0.99
    return d


def _start_drag(vp, face):
    pp = PushPullTool()
    pp.hovered_face = face
    pp._hover_group = None
    pp.on_click(ToolContext(viewport=vp, world=QVector3D(0, 0, 0),
                            screen=QPointF(400, 300),
                            modifiers=Qt.NoModifier, snap=None))
    assert pp._attached
    return pp


def _preview(vp, pp, extrusion):
    pp.extrusion = extrusion
    pp._show_light_preview(vp)
    return pp.base_face in vp.suppressed


def test_pushing_away_from_the_eye_hides_the_base_from_either_side():
    # The FRONT side toward the camera: normal +Y, eye at +Y.
    scene = Scene()
    door = _wall_with_door(scene)
    vp = _Vp(scene, eye=QVector3D(3, 10, 1))        # looks at the front
    pp = _start_drag(vp, door)
    assert _preview(vp, pp, -0.5)          # into the wall, away from the eye
    assert not _preview(vp, pp, +0.5)      # toward the eye: base is covered

    # The BACK side toward the camera — Marco's inverted face.
    scene = Scene()
    door = _wall_with_door(scene)
    vp = _Vp(scene, eye=QVector3D(3, -10, 1))       # looks at the back
    pp = _start_drag(vp, door)
    assert _preview(vp, pp, +0.5)          # away from the eye: hide the base
    assert not _preview(vp, pp, -0.5)      # toward the eye


def test_ctrl_keeps_the_base_whatever_the_camera_says():
    scene = Scene()
    door = _wall_with_door(scene)
    vp = _Vp(scene, eye=QVector3D(3, -10, 1))
    pp = _start_drag(vp, door)
    pp._keep_base = True
    assert not _preview(vp, pp, +0.5)
