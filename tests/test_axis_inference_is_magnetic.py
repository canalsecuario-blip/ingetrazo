# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""The axis inference magnetises; it does not merely light up (issue #31).

@pacaeiro: «The Soft inference of Axis (X, Y, Z) shows the message "In Red
Axis (hold Shift to lock)", but only when we hit Shift the Vector gets
aligned with the X. It should magnetically align with the axis (like other
snap point). That allows to write a distance and press Enter, finishing the
line in the vector X. Shift (to lock) is used more in conjunction with the
mouse and Snap points.»

Measured on 2026-09-18, drawing from the origin 2 m along +X with the
cursor drifting off the axis, the engine returned:

    off by 0 cm   axis_inference   y = 0.000
    off by 2 cm   axis_inference   y = 0.020
    off by 5 cm   axis_inference   y = 0.050
    off by 8 cm   axis_inference   y = 0.080

— the label said you were on the red axis and the point came back RAW. The
cue was a promise the engine did not keep, and the line went down a couple
of centimetres out of true.

The engine already knew how: the magnetic branch, which projects onto the
axis, was there for the Move tool and no drawing tool asked for it. Line
asks now, at the SOFT inference angle rather than Move's generous 15°, so
when the cue appears is unchanged and only what it returns differs.

Doing that exposed a hole in issue #26: the magnetic branch never consulted
``linear_mode``, so Alt — whose whole job is switching the linear
inferences off — did not switch this one off. Measured with Move: toggle
off, still snapped. It is gated now, which also makes Alt mean the same
thing on every tool.
"""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from PySide6.QtGui import QVector3D

from core.snap import compute_snap


def V(x, y, z=0.0):
    return QVector3D(float(x), float(y), float(z))


#: QVector3D stores float32, so a coordinate that went in as 0.40 comes
#: back as 0.4000000059604645. Compare at the precision the type has.
_EPS = 1e-6


def _w2p(p):
    """A toy projection that keeps the three axes apart on screen. Collapsing
    Z onto Y put a point 2 m up the blue axis two pixels from the origin,
    where the origin snap quite rightly won and the test measured that
    instead."""
    return (p.x() * 100.0, p.y() * 100.0 - p.z() * 100.0)


def _snap(cand, start=V(0, 0, 0), magnetic=3.0, mode="all"):
    def project(s, d):
        return s + d * QVector3D.dotProduct(cand - s, d)
    return compute_snap(
        candidate_world=cand, candidate_pixel=_w2p(cand),
        scene=SimpleNamespace(edges=[]), world_to_pixel=_w2p,
        threshold_px=9.0, edge_threshold_px=14.0, start_point=start,
        magnetic_axis_deg=magnetic, project_onto_line=project,
        linear_mode=mode)


@pytest.mark.parametrize("off", [0.0, 0.02, 0.05, 0.08])
def test_a_cursor_near_the_red_axis_lands_ON_it(off):
    r = _snap(V(2.0, off, 0.0))
    assert r.kind == "axis"
    assert r.axis == "x"
    assert r.point.y() == pytest.approx(0.0, abs=_EPS)


def test_drawing_deliberately_off_axis_is_still_possible():
    """The cone is the soft inference angle, not Move's 15°: a couple of
    degrees out and the point is yours again."""
    r = _snap(V(2.0, 0.40, 0.0))
    assert r.kind != "axis"
    assert r.point.y() == pytest.approx(0.40, abs=_EPS)


def test_the_green_and_blue_axes_too():
    assert _snap(V(0.02, 2.0, 0.0)).axis == "y"
    assert _snap(V(0.02, 0.0, 2.0)).axis == "z"


def test_alt_switches_the_magnet_off():
    """The hole in issue #26. With the linear inferences off the point must
    come back exactly where the cursor is."""
    r = _snap(V(2.0, 0.05, 0.0), mode="off")
    assert r.kind != "axis"
    assert r.point.y() == pytest.approx(0.05, abs=_EPS)


def test_and_off_for_the_move_tool_as_well():
    """Move is the tool that revealed it: its 15° magnet ignored the toggle
    entirely, so Alt did nothing at all while dragging."""
    r = _snap(V(2.0, 0.15, 0.0), magnetic=15.0, mode="off")
    assert r.kind != "axis", "Alt must reach Move's magnet too"
    assert r.point.y() == pytest.approx(0.15, abs=_EPS)


def test_with_inferences_on_move_still_magnetises_widely():
    """…and with the toggle where it normally sits, Move is unchanged: the
    generous cone is what makes dragging roughly up move straight up."""
    r = _snap(V(2.0, 0.15, 0.0), magnetic=15.0, mode="all")
    assert r.kind == "axis"
    assert r.point.y() == pytest.approx(0.0, abs=_EPS)


def test_a_point_snap_still_beats_the_magnet():
    """Magnetic or not, an endpoint you are hovering wins — otherwise the
    axis would swallow the corner you were aiming at."""
    edge = SimpleNamespace(a=V(2.0, 0.03, 0.0), b=V(3.0, 0.03, 0.0),
                           center=False)
    cand = V(2.0, 0.03, 0.0)

    def project(s, d):
        return s + d * QVector3D.dotProduct(cand - s, d)
    r = compute_snap(candidate_world=cand, candidate_pixel=_w2p(cand),
                     scene=SimpleNamespace(edges=[edge]), world_to_pixel=_w2p,
                     threshold_px=9.0, edge_threshold_px=14.0,
                     start_point=V(0, 0, 0), magnetic_axis_deg=3.0,
                     project_onto_line=project)
    assert r.kind == "endpoint"
    assert r.point.y() == pytest.approx(0.03, abs=_EPS)
