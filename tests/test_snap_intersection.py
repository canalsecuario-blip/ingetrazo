# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""Edge / guide-line intersection inference — SketchUp's green X.

Every other ``"intersection"`` in the snap engine is directional (it needs an
active lock line: an axis lock, a perpendicular draw, an extension). Two
construction guides crossing offer no such direction, so their meeting point was
never snapped: the cursor slid along whichever guide was nearest (``on_edge``).
These tests pin the general crossing snap, and that it stays out of the way —
single guides, far-from-crossing and skew guides keep their old behaviour.
"""
from __future__ import annotations

from types import SimpleNamespace

from PySide6.QtGui import QVector3D

from core.scene import Scene
from core.snap import compute_snap


def V(x: float, y: float, z: float = 0.0) -> QVector3D:
    return QVector3D(float(x), float(y), float(z))


def _w2p(p: QVector3D):
    return (p.x() * 100.0, p.y() * 100.0)


def _edge(a, b):
    """A stand-in for the viewport's ``_SnapEdge`` pseudo-edge."""
    return SimpleNamespace(a=a, b=b, center=False)


def _guide(point, direction):
    """A guide as the snap scene feeds it: a ±10 km segment (like ``Guide``)."""
    d = QVector3D(*direction).normalized()
    p = QVector3D(point)
    return _edge(p - d * 1.0e4, p + d * 1.0e4)


def _scene(*edges):
    return SimpleNamespace(edges=list(edges))


def _snap(scene, cand, **kw):
    return compute_snap(cand, _w2p(cand), scene, _w2p,
                        threshold_px=9.0, edge_threshold_px=14.0, **kw)


# ---- the crossing itself ----------------------------------------------------

def test_two_crossing_guides_snap_to_the_x():
    # A along X at y=1, B along Y at x=2 → they cross at (2, 1, 0).
    scene = _scene(_guide(V(0, 1, 0), (1, 0, 0)), _guide(V(2, 0, 0), (0, 1, 0)))
    r = _snap(scene, V(2.0, 1.0, 0.0))
    assert r.kind == "intersection"
    assert (r.point - V(2, 1, 0)).length() < 1e-3


def test_crossing_beats_on_edge_just_beside_it():
    # Cursor a few px off the X but still within the on-edge band of guide A:
    # the exact crossing must win over sliding along the guide.
    scene = _scene(_guide(V(0, 1, 0), (1, 0, 0)), _guide(V(2, 0, 0), (0, 1, 0)))
    r = _snap(scene, V(2.06, 1.05, 0.0))
    assert r.kind == "intersection"
    assert (r.point - V(2, 1, 0)).length() < 1e-3


def test_guide_crossing_a_model_edge_snaps():
    scene = Scene()
    scene.mesh.add_edge(V(0, 0, 0), V(3, 3, 0))          # a 45° model edge
    s = _scene(*scene.edges, _guide(V(0, 1, 0), (1, 0, 0)))   # guide at y=1
    r = _snap(s, V(1.0, 1.0, 0.0))                        # crossing at (1,1,0)
    assert r.kind == "intersection"
    assert (r.point - V(1, 1, 0)).length() < 1e-3


# ---- must not steal from the higher/lower-priority snaps --------------------

def test_endpoint_wins_over_intersection():
    # A real vertex sits exactly on the crossing → the endpoint snap takes it.
    scene = Scene()
    scene.mesh.add_edge(V(0, 0, 0), V(2, 1, 0))
    scene.mesh.add_edge(V(2, 1, 0), V(3, 0, 0))
    s = _scene(*scene.edges, _guide(V(0, 1, 0), (1, 0, 0)))
    r = _snap(s, V(2.01, 1.0, 0.0))
    assert r.kind == "endpoint"
    assert (r.point - V(2, 1, 0)).length() < 1e-4


def test_single_guide_still_snaps_on_edge():
    scene = _scene(_guide(V(0, 1, 0), (1, 0, 0)))
    r = _snap(scene, V(3.5, 1.0, 0.0))
    assert r.kind == "on_edge"


def test_far_from_the_crossing_is_still_on_edge():
    scene = _scene(_guide(V(0, 1, 0), (1, 0, 0)), _guide(V(2, 0, 0), (0, 1, 0)))
    r = _snap(scene, V(3.5, 1.0, 0.0))       # 1.5 m from the X
    assert r.kind == "on_edge"


def test_parallel_guides_are_not_an_intersection():
    scene = _scene(_guide(V(0, 1, 0), (1, 0, 0)), _guide(V(0, 2, 0), (1, 0, 0)))
    r = _snap(scene, V(3.5, 1.0, 0.0))
    assert r.kind != "intersection"


def test_skew_guides_do_not_invent_a_point():
    # Cross in projection but 1 m apart in Z → they never actually meet, so no
    # green X (SketchUp only marks a real crossing).
    a = _guide(V(0, 1, 0), (1, 0, 0))
    c = _guide(V(2, 0, 1), (0, 1, 0))
    scene = _scene(a, c)
    r = _snap(scene, V(2.0, 1.0, 0.0))
    assert r.kind != "intersection"


def test_occluded_crossing_is_not_offered():
    scene = _scene(_guide(V(0, 1, 0), (1, 0, 0)), _guide(V(2, 0, 0), (0, 1, 0)))
    r = _snap(scene, V(2.05, 1.05, 0.0),
              is_occluded=lambda p: (p - V(2, 1, 0)).length() < 0.5)
    assert r.kind != "intersection"
