# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""Snapping under an axis lock works in BOTH directions (issue #27).

@pacaeiro: «we activate one of the axis constraints (X, Y, Z or down arrow)
to limit the drawing or move vector, and try to get Origin, endpoint,
Midpoint, Face of an object, etc... almost none of them are detected.»

Measured with the engine on 2026-09-17, drawing from (1, 3) with the red
axis locked and the cursor four pixels off each point:

    hovering a corner    → from_point at (2.00, 3.00)   exact
    hovering a midpoint  → midpoint   at (4.00, 3.00)   exact
    hovering the ORIGIN  → axis       at (0.04, 3.00)   nothing

Two causes, and the second is the big one.

The world origin was in none of the reference lists: it is a named snap of
its own (rule 6, ``COLOR_ORIGIN``) and belongs to no edge, so under a lock
— which returns before rule 6 is ever reached — it existed only when some
geometry happened to touch it.

And the lock branch handed ``_from_point_snap`` the axis as its POSITIVE
vector whichever way the user was drawing, while that function drops every
reference behind the draw direction. So HALF THE AXIS offered nothing: the
same corner, under the same lock, snapped when approached from the left
and not from the right. A lock line runs both ways from the start; it now
points at the cursor.

Faces are a separate matter, still open with him: under a lock the engine
crosses the lock line with EDGES (rule 1b) and not with faces.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from PySide6.QtGui import QVector3D

from core.snap import compute_snap


def V(x, y, z=0.0):
    return QVector3D(float(x), float(y), float(z))


def _w2p(p):
    return (p.x() * 100.0, p.y() * 100.0)


def _edge(a, b):
    return SimpleNamespace(a=a, b=b, center=False)


def _square_away_from_the_origin():
    """A 4 m square at (2, 2)–(6, 6): nothing of it touches the origin, so
    the origin can only come from the rule that names it."""
    return SimpleNamespace(edges=[
        _edge(V(2, 2), V(6, 2)), _edge(V(6, 2), V(6, 6)),
        _edge(V(6, 6), V(2, 6)), _edge(V(2, 6), V(2, 2)),
    ])


def _snap(scene, cand, start, lock=None):
    def project(s, d):
        return s + d * QVector3D.dotProduct(cand - s, d)
    return compute_snap(cand, _w2p(cand), scene, _w2p, threshold_px=9.0,
                        edge_threshold_px=14.0, start_point=start,
                        axis_lock=lock,
                        project_onto_line=project if lock else None)


#: Drawing from here with the red axis locked, the lock line is y = 3.
START = V(1, 3)


def test_the_origin_is_found_under_an_axis_lock():
    scene = _square_away_from_the_origin()
    r = _snap(scene, V(0.04, 0.03), START, lock="x")
    assert r.kind in ("origin", "from_point"), r.kind
    assert r.point.x() == pytest.approx(0.0, abs=1e-6)
    assert r.point.y() == pytest.approx(3.0, abs=1e-6)


def test_a_corner_still_is():
    """The half that already worked, pinned."""
    scene = _square_away_from_the_origin()
    r = _snap(scene, V(2.04, 2.03), START, lock="x")
    assert r.kind == "from_point"
    assert r.point.x() == pytest.approx(2.0, abs=1e-6)


def test_a_midpoint_still_is():
    scene = _square_away_from_the_origin()
    r = _snap(scene, V(4.04, 2.03), START, lock="x")
    assert r.kind == "midpoint"
    assert r.point.x() == pytest.approx(4.0, abs=1e-6)


def test_without_a_lock_the_origin_is_the_origin():
    """Rule 6 untouched: no lock, hovering the origin names it."""
    scene = _square_away_from_the_origin()
    assert _snap(scene, V(0.04, 0.03), START).kind == "origin"


def test_the_origin_does_not_hijack_a_far_cursor():
    """It is a reference, not a magnet: a cursor nowhere near it must still
    get the plain axis point."""
    scene = _square_away_from_the_origin()
    r = _snap(scene, V(9.0, 3.0), START, lock="x")
    assert r.kind == "axis"


def test_the_side_you_draw_from_makes_no_difference():
    """The heart of #27: same corner, same lock, opposite directions.
    Drawing toward −X used to give a bare axis point four centimetres off."""
    scene = _square_away_from_the_origin()
    hacia_mas_x = _snap(scene, V(2.04, 2.03), V(1, 3), lock="x")
    hacia_menos_x = _snap(scene, V(2.04, 2.03), V(8, 3), lock="x")
    for r in (hacia_mas_x, hacia_menos_x):
        assert r.kind == "from_point", r.kind
        assert r.point.x() == pytest.approx(2.0, abs=1e-6)
        assert r.point.y() == pytest.approx(3.0, abs=1e-6)


def test_the_origin_too_from_either_side():
    scene = _square_away_from_the_origin()
    for start in (V(-5, 3), V(8, 3)):
        r = _snap(scene, V(0.04, 0.03), start, lock="x")
        assert r.kind in ("origin", "from_point"), (start, r.kind)
        assert r.point.x() == pytest.approx(0.0, abs=1e-6)


def test_it_works_on_the_other_axes_too():
    scene = _square_away_from_the_origin()
    # Drawing from (3, 1) with the GREEN axis locked: the line is x = 3.
    def project(s, d):
        return s + d * QVector3D.dotProduct(V(0.03, 0.04) - s, d)
    r = compute_snap(V(0.03, 0.04), _w2p(V(0.03, 0.04)), scene, _w2p,
                     threshold_px=9.0, edge_threshold_px=14.0,
                     start_point=V(3, 1), axis_lock="y",
                     project_onto_line=project)
    assert r.kind in ("origin", "from_point"), r.kind
    assert r.point.y() == pytest.approx(0.0, abs=1e-6)
