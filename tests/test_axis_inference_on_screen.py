# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""The third axis, the one the work plane cannot offer (issue #31).

@pacaeiro: «in certain viewport positions, is impossible to get Inference
of the 3 axis (X, Y, Z)».

Measured over the whole camera grid before changing anything (11 cameras ×
72 directions, harness in ``scripts/probe_snap_matrix.py``): every camera
reached exactly TWO axes and never three — x/y from the top, x/z from the
front, y/z from the side, and one oblique managed only one. It is geometry,
not a threshold wanting widening: the cursor becomes a world point by
landing on the work plane, the world-space detector compares directions in
that same space, and a plane holds at most two of the three axes.

The screen-space detector is consulted ONLY where the world one found
nothing, so the two axes a camera already offered keep coming from the path
they always came from. That is the safety property, and it is by
construction rather than by promise: over the 57,024-cell grid the only
transition that appeared was ``none → axis``, 633 of them, all on the Line
tool, with zero cells that already held an axis moving.
"""
from __future__ import annotations

import math
from types import SimpleNamespace

import pytest
from PySide6.QtGui import QVector3D

from core.snap import _detect_axis_on_screen


def V(x, y, z=0.0):
    return QVector3D(float(x), float(y), float(z))


def _top_view(p):
    """Looking straight down: x right, y up the screen, z into a dot."""
    return (400.0 + p.x() * 50.0, 300.0 - p.y() * 50.0)


def _front_view(p):
    """Looking along −y: x right, z up the screen, y into a dot."""
    return (400.0 + p.x() * 50.0, 300.0 - p.z() * 50.0)


def _iso(p):
    """A generic oblique where all three axes have a real screen direction."""
    return (400.0 + (p.x() - p.y()) * 35.0,
            300.0 - (p.z() * 40.0 + (p.x() + p.y()) * 18.0))


START = V(0, 0, 0)


def test_the_axis_under_the_cursor_is_found():
    """Straight up the screen in the front view is the blue axis — the one
    a ground work plane can never give you."""
    cand = V(0.0, 0.0, 2.0)
    assert _detect_axis_on_screen(
        START, cand, _front_view(cand), _front_view, 9.0) == "z"


def test_all_three_are_reachable_from_an_oblique():
    """The heart of the report: not two, three."""
    found = set()
    for cand in (V(2, 0, 0), V(0, 2, 0), V(0, 0, 2)):
        found.add(_detect_axis_on_screen(
            START, cand, _iso(cand), _iso, 9.0))
    assert found == {"x", "y", "z"}


def test_a_cursor_between_the_axes_gets_none():
    """It is a snap, not a magnet that swallows the screen."""
    cand = V(2.0, 0.5, 0.0)
    assert _detect_axis_on_screen(
        START, cand, _iso(cand), _iso, 9.0) is None


def test_what_you_POINT_AT_wins_even_if_the_world_disagrees():
    """The property to understand before judging this, and the one that
    caught the first draft of the test above.

    In an oblique view the world direction (1, 1, 0) projects onto the very
    same screen line as the blue axis, so a cursor there is offered blue —
    although in the world it is 90° away from it. That is not a bug in the
    detector, it is what screen-space inference MEANS, and it is what
    SketchUp does: the screen is the interface, and the user is pointing at
    the blue line.

    It matters less in the app than this test makes it look, because the
    candidate does not come from anywhere: it comes from the work plane.
    Over the real grid the whole delta was 633 cells of ``none → axis``,
    with nothing that already had an axis moving.
    """
    diagonal = V(2.0, 2.0, 0.0)
    assert _detect_axis_on_screen(
        START, diagonal, _iso(diagonal), _iso, 9.0) == "z"


def test_an_axis_pointing_at_the_camera_is_skipped():
    """Looking straight down, the blue axis projects to a dot: every cursor
    is 'on' it and the perpendicular distance means nothing. Without this
    guard, plan view would glue everything to blue."""
    cand = V(0.0, 0.0, 2.0)
    # The cursor sits exactly on the start point's pixel, which is where a
    # degenerate axis would claim it.
    assert _detect_axis_on_screen(
        START, cand, _top_view(START), _top_view, 9.0) != "z"


def test_the_nearest_axis_wins_when_two_are_close():
    cand = V(2.0, 0.12, 0.0)
    assert _detect_axis_on_screen(
        START, cand, _top_view(cand), _top_view, 40.0) == "x"


def test_no_reach_no_answer():
    """On top of the start point there is no direction to speak of."""
    assert _detect_axis_on_screen(
        START, START, _iso(START), _iso, 9.0) is None


def test_it_reads_the_line_both_ways():
    """An axis runs in both directions from the start point, as the arrow
    lock does — drawing backwards along red is still red."""
    cand = V(-2.0, 0.0, 0.0)
    assert _detect_axis_on_screen(
        START, cand, _top_view(cand), _top_view, 9.0) == "x"


def test_the_threshold_is_in_pixels_so_it_widens_as_you_draw_short():
    """Worth pinning because it is the feel risk Marco has to judge: a
    constant pixel tolerance is a WIDER angle at short reach. Measured on
    the grid, 10 % of directions caught an axis at 30 px of reach against
    3.4 % at 90 px. SketchUp works this way too; the number is the knob."""
    near, far = V(0.6, 0.06, 0.0), V(3.0, 0.06, 0.0)
    ang_near = math.degrees(math.atan2(0.06, 0.6))
    ang_far = math.degrees(math.atan2(0.06, 3.0))
    assert ang_near > ang_far
    assert _detect_axis_on_screen(
        START, near, _top_view(near), _top_view, 9.0) == "x"
    assert _detect_axis_on_screen(
        START, far, _top_view(far), _top_view, 9.0) == "x"


def test_the_line_tool_asks_for_it_and_nobody_else_yet():
    from tools.line import LineTool
    from tools.rectangle import RectangleTool
    assert LineTool.screen_axis_px == 9.0
    assert getattr(RectangleTool, "screen_axis_px", None) is None

def test_the_point_may_not_run_to_the_other_side_of_the_county():
    """Marco's first live test, 2026-09-18, and the reason for the cap.

    Seen edge-on an axis occupies almost no screen, so one pixel of mouse
    is metres of line. He put a point 16 km out, deleted it, and was left
    staring at empty space — with nothing bounded left in the document,
    zoom-to-extents had nothing to find and could not rescue him.

    Over the grid the honest cases sit at D/R around 1 (median 0.99, p99
    2.05, worst 4.01), so a 5x ceiling keeps every one of them and kills a
    runaway, which arrives in the thousands. When it bites, the answer
    falls through to what it would have been without screen detection at
    all — never to something new.
    """
    import core.snap as snap

    start = V(0, 0, 0)
    cand = V(0.0, 0.5, 0.0)

    def apenas_de_punta(p):
        """Blue at 14 px per metre: nearly pointing at the camera."""
        return (400.0 + p.x() * 60.0, 300.0 - p.y() * 60.0 - p.z() * 14.0)

    def lejisimos(s, d):
        return s + d * 300.0          # the line's nearest point, far away

    def pide(cap):
        previo = snap._MAX_AXIS_REACH
        snap._MAX_AXIS_REACH = cap
        try:
            return snap.compute_snap(
                candidate_world=cand, candidate_pixel=apenas_de_punta(cand),
                scene=SimpleNamespace(edges=[]), world_to_pixel=apenas_de_punta,
                threshold_px=9.0, edge_threshold_px=14.0, start_point=start,
                screen_axis_px=9.0, project_onto_line=lejisimos)
        finally:
            snap._MAX_AXIS_REACH = previo

    suelto = pide(1e9)
    assert suelto.kind == "axis"
    assert (suelto.point - start).length() > 200.0, "sin tope se dispara"

    atado = pide(5.0)
    assert atado.kind != "axis", "el tope debe descartar la inferencia"
    assert (atado.point - start).length() < 1.0, "y dejar el punto donde apuntas"


def test_the_cap_is_loose_enough_for_the_real_cases():
    """It must not cost anything that works: the worst honest ratio
    measured over the 57,024-cell grid was 4.01x."""
    from core.snap import _MAX_AXIS_REACH
    assert _MAX_AXIS_REACH > 4.01
