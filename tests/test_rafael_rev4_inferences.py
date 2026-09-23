"""Two inferences from Rafael's fourth review (video of 2026-09-23).

01:30 «hasta el final no me llega»: drawing from a gable's midpoint with a
corner acquired, the dotted 'from point' line led the cursor across the face,
and at the wall's edge «on edge» took over — the guide vanished and the length
jumped with every pixel. The edge now offers the one point of it that lines
up with the acquired corner.

03:56 «a veces te bloquea y a veces no… depende de cómo te orientes»: the
extension of a sloped roof edge only showed with empty sky behind it. The
collinearity was judged on where the cursor ray met the scene — on a wall
behind, not on the draw. It is now asked on screen as well."""
from __future__ import annotations

from types import SimpleNamespace

import pytest
from PySide6.QtGui import QVector3D

from core.snap import compute_snap


def V(x, y, z=0.0):
    return QVector3D(float(x), float(y), float(z))


def _edge(a, b):
    return SimpleNamespace(a=a, b=b, center=False)


# ---- 01:30 — on the edge, level with the acquired corner -------------------

def _plan(p):                     # Top view: x right, y up, 100 px per metre
    return (p.x() * 100.0, -p.y() * 100.0)


def test_the_edge_offers_the_point_level_with_the_acquired_corner():
    wall = _edge(V(0, 0), V(0, 5))
    corner = V(3, 2)                             # acquired, 3 m to the right
    cursor = V(0.03, 2.04)                       # on the wall, a hair off
    r = compute_snap(
        candidate_world=cursor, candidate_pixel=_plan(cursor),
        scene=SimpleNamespace(edges=[wall]), world_to_pixel=_plan,
        threshold_px=9.0, edge_threshold_px=14.0,
        start_point=V(3, 5),
        project_onto_line=lambda s, d: s + d * QVector3D.dotProduct(cursor - s, d),
        acquired_point=corner)
    assert r.kind == "from_point"
    assert r.point.x() == pytest.approx(0.0, abs=1e-6)
    assert r.point.y() == pytest.approx(2.0, abs=1e-6)   # level with it
    assert r.guide is not None


def test_without_an_acquired_point_it_is_still_on_edge():
    wall = _edge(V(0, 0), V(0, 5))
    cursor = V(0.03, 2.04)
    r = compute_snap(
        candidate_world=cursor, candidate_pixel=_plan(cursor),
        scene=SimpleNamespace(edges=[wall]), world_to_pixel=_plan,
        threshold_px=9.0, edge_threshold_px=14.0, start_point=V(3, 5),
        project_onto_line=lambda s, d: s + d * QVector3D.dotProduct(cursor - s, d))
    assert r.kind == "on_edge"


# ---- 03:56 — the extension with a wall behind the cursor -------------------

def _front(p):                    # Front view: x right, z up; y is depth
    return (p.x() * 100.0, -p.z() * 100.0)


def _ray_projector(px):
    """project_onto_line for a front view: the point of the line whose
    screen position is closest to the cursor pixel ``px``."""
    cx, cz = px[0] / 100.0, -px[1] / 100.0

    def project(s, d):
        dx, dz = d.x(), d.z()
        den = dx * dx + dz * dz
        if den < 1e-12:
            return QVector3D(s)
        t = ((cx - s.x()) * dx + (cz - s.z()) * dz) / den
        return s + d * t
    return project


def test_the_extension_shows_with_a_wall_behind_the_cursor():
    rafter = _edge(V(0, 0, 0), V(2, 0, 1))       # the sloped roof edge
    on_screen = V(3, 0, 1.5)                     # on its continuation
    behind = V(3, 5, 1.5)                        # where the ray hits a wall
    px = _front(on_screen)
    r = compute_snap(
        candidate_world=behind, candidate_pixel=px,
        scene=SimpleNamespace(edges=[rafter]), world_to_pixel=_front,
        threshold_px=9.0, edge_threshold_px=14.0,
        start_point=V(2, 0, 1), project_onto_line=_ray_projector(px))
    assert r.kind == "extension"
    assert r.point.x() == pytest.approx(3.0, abs=1e-6)
    assert r.point.y() == pytest.approx(0.0, abs=1e-6)   # on the edge's line
    assert r.point.z() == pytest.approx(1.5, abs=1e-6)
