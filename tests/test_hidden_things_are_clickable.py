# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""Issue #53 (@pacaeiro): «After we hide objects or raw geometry and
activate the (show Hidden Objects and Hidden Geometry) we cannot select
them with mouse click, only by window selection.»

The pick index's group block is keyed on the placements epoch, which knew
each group's ``hidden`` but not the two view switches: Hide rebuilt the
block without the object, and switching the view on reused it. The order
matters — a pick between the two steps is what left the stale block."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QMatrix4x4, QVector3D  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

if QApplication.instance() is None:
    QApplication([])

from core.group import Group  # noqa: E402
from core.mesh import Mesh  # noqa: E402
from views.viewport import Viewport  # noqa: E402


def V(x, y, z=0.0):
    return QVector3D(float(x), float(y), float(z))


def _vp():
    vp = Viewport(None)
    vp.resize(1000, 600)
    vp.camera.set_aspect(1000, 600)
    vp.flash_status = lambda *a, **k: None
    vp.camera.set_view("top")
    vp.camera.target = V(3, 3, 0)
    vp.camera.distance = 12
    return vp


def _boxed_group(vp):
    m = Mesh()
    m.add_face([V(0, 0, 0), V(2, 0, 0), V(2, 2, 0), V(0, 2, 0)])
    g = Group(m, "caja")
    xf = QMatrix4x4()
    xf.translate(1, 1, 0)
    g.xform = xf
    vp.scene.groups.append(g)
    vp.scene.version += 1
    return g


def test_a_hidden_object_shown_as_a_ghost_takes_the_click():
    vp = _vp()
    sc = vp.scene
    g = _boxed_group(vp)
    px = vp._world_to_pixel(V(2, 2, 0))
    assert vp.pick_group(*px) is g
    g.hidden = True
    sc.version += 1
    assert vp.pick_group(*px) is None                 # hidden: gone
    sc.show_hidden_objects = True                     # View ▸ Hidden Objects
    sc.version += 1
    assert vp.pick_group(*px) is g                    # the ghost is clickable
    sc.show_hidden_objects = False
    sc.version += 1
    assert vp.pick_group(*px) is None


def test_a_hidden_face_shown_as_a_ghost_takes_the_click():
    vp = _vp()
    sc = vp.scene
    f = sc.mesh.add_face([V(0, 0, 0), V(2, 0, 0), V(2, 2, 0), V(0, 2, 0)])
    sc.version += 1
    px = vp._world_to_pixel(V(1, 1, 0))
    assert vp.pick_face(*px) is f
    f.attrs = dict(getattr(f, "attrs", None) or {}, hidden=True)
    sc.version += 1
    assert vp.pick_face(*px) is None
    sc.show_hidden_geometry = True
    sc.version += 1
    assert vp.pick_face(*px) is f


def test_a_hidden_edge_is_clickable_only_while_shown():
    vp = _vp()
    sc = vp.scene
    e = sc.mesh.add_edge(V(0, 0, 0), V(4, 0, 0))
    sc.version += 1
    px = vp._world_to_pixel(V(2, 0, 0))
    assert vp.pick_edge(*px) is e
    e.hidden = True
    sc.version += 1
    assert vp.pick_edge(*px) is None                  # as window selection
    sc.show_hidden_geometry = True
    sc.version += 1
    assert vp.pick_edge(*px) is e
