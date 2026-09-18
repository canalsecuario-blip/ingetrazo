# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""An acquired point keeps guiding you once you have started drawing.

Marco, screen recording of 2026-09-18, drawing the step of exercise 18 along
a wall: «quiero dibujar un rectángulo en el suelo agarrado de las dos
esquinas del muro, en la segunda esquina está la referencia pero al momento
de jalar el rectángulo se pierde la referencia».

The plane was right and the corner was found — the recording shows
«Intersección» with its green X at 6.43 x 0.00 m. Pulling out to give the
step its depth, the length slid to 6.37: nothing held it to the corner.

Measured with the corner acquired and the same cursor:

    before the first click     from_point   x = 6.430
    rectangle under way        none         x = 6.370

The machinery was built and working. It was locked away behind
``start_point is None`` at exactly the moment he needed it, and SketchUp
offers it mid-operation too.

WHERE it was opened is the whole safety argument. Rule 5d sits ABOVE the
named points, so unlocking it in place would have let an alignment line
outrank a midpoint or the origin — precedence that is not ours to spend.
The mid-operation call is a second one, further down, competing only with
the soft axis cue. Over the 114,048-cell grid: 1368 cells changed, every one
of them into ``from_point``, none of them without an acquired point, and not
one named point overridden.
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


#: Marco's wall, to the centimetre: the step runs its 6.43 m.
INICIO = V(0, 0, 0)
ESQUINA = V(6.43, 0, 0)


def _snap(cand, start=INICIO, acquired=ESQUINA, scene=None, mode="all"):
    def project(s, d):
        return s + d * QVector3D.dotProduct(cand - s, d)
    return compute_snap(
        candidate_world=cand, candidate_pixel=_w2p(cand),
        scene=scene or SimpleNamespace(edges=[
            SimpleNamespace(a=INICIO, b=ESQUINA, center=False)]),
        world_to_pixel=_w2p, threshold_px=9.0, edge_threshold_px=14.0,
        start_point=start, project_onto_line=project if start else None,
        acquired_point=acquired, linear_mode=mode)


@pytest.mark.parametrize("depth", [0.40, 0.90, 1.50])
def test_the_length_stays_on_the_corner_while_you_pull_the_depth(depth):
    r = _snap(V(6.37, depth, 0.0))
    assert r.kind == "from_point"
    assert r.point.x() == pytest.approx(6.43, abs=1e-6), "the wall's end"


def test_without_an_acquired_point_nothing_changes():
    """The rule cannot fire on its own — measured over the whole grid, not a
    single cell moved with no point acquired."""
    r = _snap(V(6.37, 0.90, 0.0), acquired=None)
    assert r.kind != "from_point"
    assert r.point.x() == pytest.approx(6.37, abs=1e-6)


def test_a_named_point_still_wins():
    """The precedence that had to be protected: the mid-operation call sits
    BELOW the named points, so a midpoint the cursor is on still takes it."""
    edge = SimpleNamespace(a=V(6.43, 0.80, 0.0), b=V(6.43, 1.00, 0.0),
                           center=False)
    r = _snap(V(6.43, 0.90, 0.0),
              scene=SimpleNamespace(edges=[edge]))
    assert r.kind == "midpoint"


def test_alt_switches_it_off_like_every_other_linear_inference():
    r = _snap(V(6.37, 0.90, 0.0), mode="off")
    assert r.kind != "from_point"


def test_it_still_works_before_the_first_click():
    """Rule 5d, untouched — this is the half that always worked."""
    r = _snap(V(6.37, 0.40, 0.0), start=None)
    assert r.kind == "from_point"
    assert r.point.x() == pytest.approx(6.43, abs=1e-6)


def test_a_midpoint_beats_the_alignment_line_on_the_first_click():
    """Marco's A1, 2026-09-18, and the reason this rule moved house.

    He clicked the midpoint of a 4 m line and the drawing came out 2.8 cm
    off — reported twice before it was caught («del medio de la línea
    quiero dibujar una línea, dibujo sale desfasada»). Reading his scene
    through the bridge: the line ran 2.2390 → 6.2390, so its middle is
    4.2390, and his click had landed at 4.2670, leaving halves of 2.0280
    and 1.9720.

    He had acquired the line's own left END, whose alignment line runs
    straight along the line itself — so it covered the midpoint for the
    whole length. Reproduced with his exact geometry and camera:

        nothing acquired     midpoint     0.00 cm
        one end acquired     from_point   0.65 cm

    An alignment LINE was beating a named POINT. The rule used to sit above
    them AND only before the first click; both halves were wrong.
    """
    a, b = V(2.0, 1.0, 0.0), V(6.0, 1.0, 0.0)
    medio = V(4.0, 1.0, 0.0)
    escena = SimpleNamespace(edges=[SimpleNamespace(a=a, b=b, center=False)])
    r = compute_snap(
        candidate_world=medio, candidate_pixel=_w2p(medio), scene=escena,
        world_to_pixel=_w2p, threshold_px=9.0, edge_threshold_px=14.0,
        start_point=None, acquired_point=a)
    assert r.kind == "midpoint"
    assert r.point.x() == pytest.approx(4.0, abs=1e-6)


def test_the_alignment_still_answers_where_no_named_point_does():
    """Rafael's window, which is what the rule was built for: level with
    the door's top, out in the open where nothing else competes."""
    escena = SimpleNamespace(edges=[])
    cand = V(5.0, 1.02, 0.0)
    r = compute_snap(
        candidate_world=cand, candidate_pixel=_w2p(cand), scene=escena,
        world_to_pixel=_w2p, threshold_px=9.0, edge_threshold_px=14.0,
        start_point=None, acquired_point=V(2.0, 1.0, 0.0))
    assert r.kind == "from_point"
    assert r.point.y() == pytest.approx(1.0, abs=1e-6)
