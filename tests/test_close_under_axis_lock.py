# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""An axis lock must not trap you inside the polyline (found live, 2026-09-18).

Marco, grading exercise 2 of the inference test: «se cerró la figura, lo que
no entiendo es que con rótulo te refieres al eje x bloqueado? sigue
apareciendo el eje x bloqueado».

He marked it "did not understand". It was a failure, and the label was
telling the truth: the figure had NOT closed. Measured with a chain starting
at (2, 5) and the cursor back on that point:

    no lock              kind = close   → the chain ends
    red axis locked      kind = axis    → the chain goes on

Rule 1 returns before rule 4 is ever reached, so the click that should have
closed the polyline came back as a plain axis point. It LOOKED closed —
the point does land exactly where it belongs — and the lock stayed on
because the operation had never actually ended. The axis-lock release
shipped that morning was working; there was simply no end for it to fire at.

The same early return hid the world origin in issue #27. This is its third
victim.
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


PRIMERO = V(2.0, 5.0, 0.0)      # where the chain began
ACTUAL = V(6.0, 5.0, 0.0)       # the vertex it is drawing from


def _snap(cursor, lock, first=PRIMERO, scene=None):
    def project(s, d):
        return s + d * QVector3D.dotProduct(cursor - s, d)
    return compute_snap(
        candidate_world=cursor, candidate_pixel=_w2p(cursor),
        scene=scene or SimpleNamespace(edges=[]), world_to_pixel=_w2p,
        threshold_px=9.0, edge_threshold_px=14.0, start_point=ACTUAL,
        chain_first_point=first, axis_lock=lock, project_onto_line=project)


def test_the_chain_closes_with_the_axis_locked():
    r = _snap(V(2.02, 5.01, 0.0), "x")
    assert r.kind == "close"
    assert r.point.x() == pytest.approx(2.0, abs=1e-6)
    assert r.point.y() == pytest.approx(5.0, abs=1e-6)


def test_and_still_closes_without_one():
    """The half that always worked, pinned."""
    assert _snap(V(2.02, 5.01, 0.0), None).kind == "close"


def test_a_first_point_OFF_the_lock_line_does_not_break_the_lock():
    """Held to the same standard as the endpoint rule beside it: closing
    must never quietly cancel the constraint the user asked for. The lock
    runs along y = 5; a chain that began a metre off it stays unreachable
    until Esc drops the lock."""
    r = _snap(V(2.02, 6.01, 0.0), "x", first=V(2.0, 6.0, 0.0))
    assert r.kind != "close"


def test_a_cursor_nowhere_near_it_still_gets_the_axis():
    """It is a snap, not a magnet: the close point has to be under the
    cursor."""
    assert _snap(V(4.5, 5.0, 0.0), "x").kind == "axis"


def test_an_endpoint_on_the_line_is_unaffected():
    """Rule 1a still answers for ordinary vertices — the new rule only
    speaks for the chain's own first point."""
    edge = SimpleNamespace(a=V(3.0, 5.0, 0.0), b=V(3.0, 7.0, 0.0),
                           center=False)
    r = _snap(V(3.01, 5.01, 0.0), "x",
              scene=SimpleNamespace(edges=[edge]))
    assert r.kind == "endpoint"
