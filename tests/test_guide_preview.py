"""The guide the Tape or the Protractor is about to leave shows, dashed,
while the cursor moves — also in perspective, where a guide kilometres long
has one end behind the eye and the old preview dropped it whole (#89,
@pacaeiro)."""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QVector3D

from core.guide import Guide
from core.history import History
from core.scene import Scene
from tools.base import ToolContext
from tools.protractor import ProtractorTool
from tools.tape import TapeMeasureTool


class _Vp:
    def __init__(self, scene):
        self.scene = scene
        self.history = History(scene)

    def update(self):
        pass

    def flash_status(self, *a, **k):
        pass


def _ctx(vp, x, y, z=0.0):
    return ToolContext(viewport=vp, world=QVector3D(x, y, z),
                       screen=QPointF(x * 100.0, y * 100.0),
                       modifiers=Qt.NoModifier, snap=None)


def test_the_protractor_shows_the_guide_before_the_click():
    vp = _Vp(Scene())
    t = ProtractorTool()
    t.on_activate(vp)
    t.on_click(_ctx(vp, 2, 1))                    # vertex
    assert t.guide_preview_lines() == []
    t.on_click(_ctx(vp, 5, 1))                    # base arm = +X
    t.on_hover(_ctx(vp, 2, 4))                    # sweeping to 90°
    (a, b), = t.guide_preview_lines()
    d = (b - a).normalized()
    assert abs(d.x()) < 1e-6 and abs(abs(d.y()) - 1.0) < 1e-6
    assert (a - b).length() > 1000.0              # a guide, not a stub
    t._guides = False                             # Ctrl: measure only
    assert t.guide_preview_lines() == []


def test_the_tape_shows_the_parallel_guide_before_the_click():
    vp = _Vp(Scene())
    t = TapeMeasureTool()
    t.on_activate(vp)
    t.start_point = QVector3D(0, 0, 0)
    t._edge = Guide(QVector3D(0, 0, 0), QVector3D(1, 0, 0))   # pulled off X
    t.hover_point = QVector3D(3, 2, 0)
    (a, b), = t.guide_preview_lines()
    assert abs(a.y() - 2.0) < 1e-6 and abs(b.y() - 2.0) < 1e-6
    t._mode = "measure"
    t._edge = None
    assert t.guide_preview_lines() == []


def test_a_guide_through_the_eye_still_reaches_the_screen():
    from views.viewport import Viewport
    vp = Viewport()
    vp.resize(800, 600)
    cam = vp.camera
    cam.set_aspect(800, 600)
    cam.target = QVector3D(0, 0, 0)
    cam.yaw, cam.pitch, cam.distance = math.radians(-60), math.radians(20), 10
    # A guide along the sight line, from far behind the eye to far ahead.
    f = cam.forward()
    g = Guide(cam.target + QVector3D(0.5, 0.5, 0), f)
    a, b = g.segment()
    assert vp._world_to_pixel(a) is None          # one end behind the eye
    q = vp._segment_to_pixels(a, b)
    assert q is not None
    for x, y in q:
        assert -65 <= x <= 865 and -65 <= y <= 665
