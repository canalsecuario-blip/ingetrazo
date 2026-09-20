# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""The section cap — «tapa pero no tapa» (Rafael, 2026-09-16, 46:00–49:30).

A cut leaves the solid open, so the hidden-line pass used to look straight
through the wall it had just sliced and ink the far side of the board across
the poché; the fill mode changed nothing, because the fill is painted UNDER
the lines. The rings the composer fills now occlude too, under the same
even-odd rule — a hollow wall's hole stays see-through, and the cut outline,
which lies ON the plane, always survives.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest
from PySide6.QtGui import QVector3D
from PySide6.QtWidgets import QApplication

from core.camera import OrbitCamera
from core.composition import MarcoVista, apply_frame_camera
from core.hlr import KIND_CUT, hlr_drawing
from core.scene import Scene
from core.section import SectionPlane

_app = QApplication.instance() or QApplication([])
V = QVector3D


def _box(m, x0, y0, z0, x1, y1, z1):
    """A closed axis-aligned box of six faces."""
    m.add_face([V(x0, y0, z0), V(x1, y0, z0), V(x1, y1, z0), V(x0, y1, z0)])
    m.add_face([V(x0, y0, z1), V(x1, y0, z1), V(x1, y1, z1), V(x0, y1, z1)])
    m.add_face([V(x0, y0, z0), V(x1, y0, z0), V(x1, y0, z1), V(x0, y0, z1)])
    m.add_face([V(x0, y1, z0), V(x1, y1, z0), V(x1, y1, z1), V(x0, y1, z1)])
    m.add_face([V(x0, y0, z0), V(x0, y1, z0), V(x0, y1, z1), V(x0, y0, z1)])
    m.add_face([V(x1, y0, z0), V(x1, y1, z0), V(x1, y1, z1), V(x1, y0, z1)])


def _front(scene):
    """The camera of a std:front sheet frame: looking along +Y, so a plane
    that keeps y ≥ cut opens its hole straight at us."""
    cam = OrbitCamera()
    apply_frame_camera(
        cam, MarcoVista(view_key="std:front", scale_n=100.0,
                        w_mm=100.0, h_mm=100.0),
        saved_view=None, scene=scene)
    return cam


def _cut_at_y(scene, y: float) -> SectionPlane:
    """Slice away everything nearer than *y*: the front view looks into it."""
    sp = SectionPlane(V(0, y, 0), V(0, -1, 0))
    scene.section_planes.append(sp)
    scene.set_active_section(sp)
    return sp


def _inked_near(d, x: float, y: float, tol: float = 0.05) -> bool:
    """Is any drawn segment passing within *tol* of the drawing point?"""
    for (x0, y0, x1, y1) in d.segs:
        dx, dy = x1 - x0, y1 - y0
        ln2 = dx * dx + dy * dy
        t = 0.0 if ln2 == 0.0 else ((x - x0) * dx + (y - y0) * dy) / ln2
        t = min(1.0, max(0.0, t))
        if np.hypot(x0 + t * dx - x, y0 + t * dy - y) <= tol:
            return True
    return False


def _cut_length(d) -> float:
    return float(sum(np.hypot(x1 - x0, y1 - y0)
                     for (x0, y0, x1, y1), k in zip(d.segs, d.kinds)
                     if k == KIND_CUT))


# ---- the bug Rafael kept coming back to ------------------------------------

def test_the_poche_hides_the_board_behind_the_cut():
    """A box with another box inside it, cut across: the inner box used to
    be inked right over the poché."""
    scene = Scene()
    _box(scene.mesh, 0, 0, 0, 4, 6, 4)            # the outer solid
    _box(scene.mesh, 1, 3, 1, 3, 5, 3)            # a board behind the cut
    _cut_at_y(scene, 2.0)
    cam = _front(scene)

    # The net can express the failure: without the cap, the board is inked
    # (and that is exactly what the sheet showed).
    open_cut = hlr_drawing(scene, cam, caps=False)
    assert _inked_near(open_cut, 0.0, -1.0), "the board should show uncapped"

    d = hlr_drawing(scene, cam)
    assert not _inked_near(d, 0.0, -1.0)          # its bottom edge
    assert not _inked_near(d, 0.0, 1.0)           # its top edge
    assert not _inked_near(d, -1.0, 0.0)          # its left edge
    assert not _inked_near(d, 1.0, 0.0)           # its right edge
    # nothing at all is drawn strictly inside the poché any more
    for (x0, y0, x1, y1) in d.segs:
        assert max(abs(x0), abs(y0), abs(x1), abs(y1)) >= 2.0 - 1e-6
    # and the cut outline — it lies ON the plane — survives whole
    assert len(d.loops) == 1
    assert _cut_length(d) >= 4 * 4 - 1e-6


def test_a_hollow_wall_keeps_its_hole_see_through():
    """Even-odd, the rule the poché is painted with: the band of the wall
    covers, the hole in the middle does not."""
    scene = Scene()
    _box(scene.mesh, 0, 0, 0, 6, 8, 4)            # outer skin
    _box(scene.mesh, 1, 0, 1, 5, 8, 3)            # inner skin: a tube
    _box(scene.mesh, 2, 3, 1.5, 4, 5, 2.5)        # a marker inside the hole
    _box(scene.mesh, 0.2, 3, 0.2, 0.8, 5, 0.8)    # a marker inside the wall
    _cut_at_y(scene, 2.0)
    cam = _front(scene)
    d = hlr_drawing(scene, cam)

    assert len(d.loops) == 2                      # outer ring + its hole
    # Both markers are inked without the cap — the net can tell them apart
    # only because it probes their EDGES, not their middles.
    open_cut = hlr_drawing(scene, cam, caps=False)
    for probe in ((-1.0, 0.0), (0.0, -0.5), (-2.5, -1.8), (-2.8, -1.5)):
        assert _inked_near(open_cut, *probe)
    # inside the hole: genuinely visible through the opening, and it stays
    assert _inked_near(d, -1.0, 0.0)              # the marker's left edge
    assert _inked_near(d, 0.0, -0.5)              # its bottom edge
    # inside the wall band: buried in solid material, so gone
    assert not _inked_near(d, -2.5, -1.8)
    assert not _inked_near(d, -2.8, -1.5)
    assert not _inked_near(d, -2.2, -1.5)
    assert not _inked_near(d, -2.5, -1.2)


def test_an_edge_on_cut_draws_its_open_silhouette():
    """A plane seen edge-on caps nothing — its region projects to a line,
    and asking for a cap must not blank the drawing or blow up."""
    scene = Scene()
    _box(scene.mesh, 0, 0, 0, 4, 6, 4)
    sp = SectionPlane(V(0, 0, 2), V(0, 0, -1))    # horizontal, seen from the front
    scene.section_planes.append(sp)
    scene.set_active_section(sp)
    d = hlr_drawing(scene, _front(scene))
    assert len(d.segs) > 0
    assert _cut_length(d) > 0


def test_the_cap_does_not_touch_a_drawing_without_a_section():
    scene = Scene()
    _box(scene.mesh, 0, 0, 0, 4, 6, 4)
    cam = _front(scene)
    a = hlr_drawing(scene, cam)
    b = hlr_drawing(scene, cam, caps=False)
    assert a.segs.shape == b.segs.shape
    assert np.allclose(a.segs, b.segs)


@pytest.mark.parametrize("fill", ["solid", "hatch", "none"])
def test_the_cover_does_not_depend_on_the_fill_mode(fill):
    """«Con relleno Sólido pasa lo mismo»: covering is the cut's job, not
    the fill's — the composer only asks for the rings when it paints them."""
    scene = Scene()
    _box(scene.mesh, 0, 0, 0, 4, 6, 4)
    _box(scene.mesh, 1, 3, 1, 3, 5, 3)
    _cut_at_y(scene, 2.0)
    d = hlr_drawing(scene, _front(scene), fills=(fill != "none"))
    assert not _inked_near(d, 0.0, -1.0)
    assert len(d.loops) == (0 if fill == "none" else 1)
