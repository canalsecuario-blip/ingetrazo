# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""Shift's lock offers the same snaps the arrow lock does (issue #31).

@pacaeiro, testing 0.4.4: «Right now, when I get an Axis (X for example) and
locked it with Shift, I do not have any Snaps. The use of the Shift is good
especially for that, to use with the mouse and get points from other
objects. P.S.- If I use hard lock (arrows) I have the Snaps working.»

He is right, and he also says why it matters: Shift is the lock you reach
for precisely so you can hold a direction and go fetch a point from
somewhere else. Held to a direction with nothing to fetch, it is half a
tool.

Issue #27 gave the ARROW lock three sub-rules — a vertex on the lock line,
the crossing with another edge, and a corner or midpoint projected onto it.
Rule 1.5, Shift's sticky lock, only ever had the first, and only for a
vertex sitting exactly on the line. It has all three now, in the same
order, plus the both-ways direction fix from the same issue.

NOTE FOR WHOEVER COMES NEXT: ``scripts/probe_snap_matrix.py`` cannot see any
of this — ``_reset_tool`` clears ``_shift_lock`` on every cell, so the grid
reports zero changes for it. Fifth blind spot found in that net in two days.
These tests are the only thing guarding it.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from PySide6.QtGui import QVector3D

from core.snap import compute_snap


def V(x, y, z=0.0):
    return QVector3D(float(x), float(y), float(z))


def _w2p(p):
    return (p.x() * 100.0, -p.y() * 100.0)


INICIO = V(0, 0, 0)
#: A box off to the right, to go and fetch points from while locked.
CAJA = [SimpleNamespace(a=V(2, -1), b=V(6, -1), center=False),
        SimpleNamespace(a=V(6, -1), b=V(6, 3), center=False)]


def _snap(cand, lock=V(1, 0, 0), scene=None):
    def project(s, d):
        return s + d * QVector3D.dotProduct(cand - s, d)
    return compute_snap(
        candidate_world=cand, candidate_pixel=_w2p(cand),
        scene=scene if scene is not None else SimpleNamespace(edges=CAJA),
        world_to_pixel=_w2p, threshold_px=9.0, edge_threshold_px=14.0,
        start_point=INICIO, project_onto_line=project, shift_lock_dir=lock)


def test_a_midpoint_is_reachable_while_shift_holds_the_axis():
    assert _snap(V(6.0, 1.0, 0.0)).kind == "midpoint"


def test_so_is_the_crossing_with_another_edge():
    assert _snap(V(6.0, 0.0, 0.0)).kind == "intersection"


def test_and_a_corner_lines_up_onto_the_locked_line():
    assert _snap(V(6.0, -1.0, 0.0)).kind == "from_point"


def test_a_vertex_ON_the_line_still_wins_outright():
    """The one sub-rule Shift already had, pinned so it is not lost."""
    borde = SimpleNamespace(a=V(4, 0), b=V(4, 2), center=False)
    r = _snap(V(4.0, 0.0, 0.0), scene=SimpleNamespace(edges=[borde]))
    assert r.kind == "endpoint"
    assert r.point.x() == pytest.approx(4.0, abs=1e-6)


def test_the_lock_still_holds_where_there_is_nothing_to_snap_to():
    """It is a lock, not a magnet farm: out in the open it keeps the
    direction and returns the plain locked point."""
    r = _snap(V(9.0, 0.6, 0.0), scene=SimpleNamespace(edges=[]))
    assert r.kind == "reference"
    assert r.point.y() == pytest.approx(0.0, abs=1e-6)


def test_it_reads_the_lock_line_both_ways():
    """The other half of issue #27, which rule 1.5 never got either: a lock
    runs in both directions from the start point, so drawing backwards must
    offer the same points."""
    izquierda = [SimpleNamespace(a=V(-6, -1), b=V(-2, -1), center=False),
                 SimpleNamespace(a=V(-6, -1), b=V(-6, 3), center=False)]
    assert _snap(V(-6.0, 1.0, 0.0),
                 scene=SimpleNamespace(edges=izquierda)).kind == "midpoint"
