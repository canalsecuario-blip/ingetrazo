# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""Fillet — rounding the edges of a solid (Rafael's C3, 2026-09-10).

One edge of a box becomes a tangent strip with the end caps cut to the
arc; a rim of four edges becomes a chain with mitred joins; all twelve
edges add spherical corners. Every result is a closed solid whose volume
drops by exactly the rounded-off material; what cannot be rounded is
refused with a reason and the mesh is left untouched.
"""
from __future__ import annotations

import math

import pytest
from PySide6.QtGui import QVector3D

from core.fillet import apply_fillet, plan_fillet
from core.mesh import Mesh
from core.orient import is_closed, signed_volume


def box(L=2.0, W=1.0, H=1.0) -> Mesh:
    """A box with outward-wound faces, corner at the origin."""
    m = Mesh()
    p = QVector3D
    loops = [
        [p(0, 0, 0), p(0, W, 0), p(L, W, 0), p(L, 0, 0)],      # bottom −Z
        [p(0, 0, H), p(L, 0, H), p(L, W, H), p(0, W, H)],      # top +Z
        [p(0, 0, 0), p(L, 0, 0), p(L, 0, H), p(0, 0, H)],      # front −Y
        [p(L, 0, 0), p(L, W, 0), p(L, W, H), p(L, 0, H)],      # right +X
        [p(L, W, 0), p(0, W, 0), p(0, W, H), p(L, W, H)],      # back +Y
        [p(0, W, 0), p(0, 0, 0), p(0, 0, H), p(0, W, H)],      # left −X
    ]
    for lp in loops:
        m.add_face(lp)
    return m


def edge_at(m, a, b):
    va, vb = m.vertex_at(QVector3D(*a)), m.vertex_at(QVector3D(*b))
    assert va is not None and vb is not None
    e = m.find_edge(va, vb)
    assert e is not None
    return e


def rounded_off(radius, length):
    """Material removed by one 90° fillet along ``length``."""
    return (radius ** 2 - math.pi * radius ** 2 / 4.0) * length


def test_one_edge_becomes_a_tangent_strip_and_the_caps_get_the_arc():
    m = box()
    e = edge_at(m, (0, 0, 1), (2, 0, 1))          # top-front edge, along X
    plan = plan_fillet(m, [e], 0.2, 8)
    assert not isinstance(plan, str), plan
    apply_fillet(m, plan)
    assert len(m.faces) == 6 + 8
    assert is_closed(m)
    # Every strip point is 0.2 from the cylinder axis (y = 0.2, z = 0.8).
    for f in m.faces[6:]:
        for q in f.vertices:
            assert abs(math.hypot(q.y() - 0.2, q.z() - 0.8) - 0.2) < 1e-6
    # The top face was cut back to y = 0.2, the front face to z = 0.8.
    top = [f for f in m.faces if all(abs(q.z() - 1.0) < 1e-9 for q in f.vertices)]
    assert len(top) == 1 and min(q.y() for q in top[0].vertices) == pytest.approx(0.2)
    front = [f for f in m.faces if all(abs(q.y()) < 1e-9 for q in f.vertices)]
    assert len(front) == 1 and max(q.z() for q in front[0].vertices) == pytest.approx(0.8)
    # The end caps carry the arc: 4 corners − 1 + 9 arc points.
    caps = [f for f in m.faces if all(abs(q.x()) < 1e-9 for q in f.vertices)]
    assert len(caps) == 1 and len(caps[0].vertices) == 3 + 9
    # Volume: the box minus the rounded-off material (a polygonal arc
    # leaves a hair more than the exact circle).
    vol = abs(signed_volume(m))
    assert 2.0 - rounded_off(0.2, 2.0) - 0.002 < vol < 2.0 - rounded_off(0.2, 2.0) + 0.002
    # Seams soft, cap arcs tagged as curves and NOT soft.
    soft = [e for e in m.edges if e.soft]
    curves = {e.curve for e in m.edges if e.curve is not None}
    assert len(soft) == 9                # 7 seams + the 2 tangent lines
    assert len(curves) == 2
    assert all(not e.soft for e in m.edges if e.curve is not None)


def test_the_top_rim_is_a_chain_with_mitred_joins():
    m = box(2.0, 1.0, 1.0)
    rim = [edge_at(m, (0, 0, 1), (2, 0, 1)), edge_at(m, (2, 0, 1), (2, 1, 1)),
           edge_at(m, (2, 1, 1), (0, 1, 1)), edge_at(m, (0, 1, 1), (0, 0, 1))]
    plan = plan_fillet(m, rim, 0.2, 8)
    assert not isinstance(plan, str), plan
    apply_fillet(m, plan)
    assert len(m.faces) == 6 + 4 * 8
    assert is_closed(m)
    top = [f for f in m.faces if all(abs(q.z() - 1.0) < 1e-9 for q in f.vertices)]
    assert len(top) == 1
    xs = sorted(q.x() for q in top[0].vertices)
    assert xs[0] == pytest.approx(0.2) and xs[-1] == pytest.approx(1.8)
    # The vertical edges now start at z = 0.8 (the mitre section's end).
    left_front = [e for e in m.edges
                  if abs(e.a.x()) < 1e-9 and abs(e.b.x()) < 1e-9
                  and abs(e.a.y()) < 1e-9 and abs(e.b.y()) < 1e-9]
    assert len(left_front) == 1
    assert max(left_front[0].a.z(), left_front[0].b.z()) == pytest.approx(0.8)
    # No curve on the mitre sections: they are inside the rounding.
    assert not any(e.curve is not None for e in m.edges)


def test_all_twelve_edges_add_spherical_corners():
    m = box(2.0, 1.0, 1.0)
    plan = plan_fillet(m, list(m.edges), 0.2, 8)
    assert not isinstance(plan, str), plan
    apply_fillet(m, plan)
    assert len(m.faces) == 6 + 12 * 8 + 8 * 64
    assert is_closed(m)
    # Corner patch points sit on the sphere about (0.2, 0.2, 0.2) etc.
    centre = QVector3D(0.2, 0.2, 0.2)
    near = [f for f in m.faces if len(f.vertices) == 3
            and all(q.x() < 0.21 and q.y() < 0.21 and q.z() < 0.21 for q in f.vertices)]
    assert len(near) == 64
    for f in near:
        for q in f.vertices:
            assert abs((q - centre).length() - 0.2) < 1e-6
    assert all(e.soft for e in m.edges)
    vol = abs(signed_volume(m))
    assert 1.80 < vol < 1.90          # 2.0 minus the edges and the corners


def test_a_concave_edge_rounds_into_the_hollow():
    """An L-shaped block: the inside corner gets a concave fillet — the
    material grows there and the solid stays closed."""
    m = Mesh()
    p = QVector3D
    # Footprint: an L (2×2 minus the 1×1 top-right square), height 1.
    foot = [p(0, 0, 0), p(2, 0, 0), p(2, 1, 0), p(1, 1, 0), p(1, 2, 0), p(0, 2, 0)]
    m.add_face(list(reversed(foot)))                          # bottom −Z
    m.add_face([p(q.x(), q.y(), 1.0) for q in foot])          # top +Z
    n = len(foot)
    for i in range(n):
        a, b = foot[i], foot[(i + 1) % n]
        m.add_face([a, b, p(b.x(), b.y(), 1.0), p(a.x(), a.y(), 1.0)])
    assert is_closed(m)
    v0 = abs(signed_volume(m))
    e = edge_at(m, (1, 1, 0), (1, 1, 1))                       # the inside corner
    plan = plan_fillet(m, [e], 0.2, 8)
    assert not isinstance(plan, str), plan
    apply_fillet(m, plan)
    assert is_closed(m)
    assert abs(signed_volume(m)) > v0 + 0.5 * rounded_off(0.2, 1.0)
    # The strip curves around a centre OUTSIDE the material: (1.2, 1.2).
    for f in m.faces[8:]:
        for q in f.vertices:
            assert abs(math.hypot(q.x() - 1.2, q.y() - 1.2) - 0.2) < 1e-6


def test_an_oblique_end_cap_is_cut_on_its_own_plane():
    m = Mesh()
    p = QVector3D
    loops = [[p(0, 0, 0), p(0, 1, 0), p(2, 1, 0), p(2.5, 0, 0)],
             [p(0, 0, 1), p(2.5, 0, 1), p(2, 1, 1), p(0, 1, 1)],
             [p(0, 0, 0), p(2.5, 0, 0), p(2.5, 0, 1), p(0, 0, 1)],
             [p(2.5, 0, 0), p(2, 1, 0), p(2, 1, 1), p(2.5, 0, 1)],
             [p(2, 1, 0), p(0, 1, 0), p(0, 1, 1), p(2, 1, 1)],
             [p(0, 1, 0), p(0, 0, 0), p(0, 0, 1), p(0, 1, 1)]]
    for lp in loops:
        m.add_face(lp)
    e = edge_at(m, (0, 0, 1), (2.5, 0, 1))
    plan = plan_fillet(m, [e], 0.2, 8)
    assert not isinstance(plan, str), plan
    apply_fillet(m, plan)
    assert is_closed(m)
    # The slanted cap keeps its plane (x + 0.5·y = 2.5) through the arc.
    cap = [f for f in m.faces if len(f.vertices) > 4
           and all(abs(q.x() + 0.5 * q.y() - 2.5) < 1e-6 for q in f.vertices)]
    assert len(cap) == 1


def test_refusals_leave_the_mesh_untouched():
    m = box()
    faces, edges = len(m.faces), len(m.edges)
    # Too large for the box height.
    msg = plan_fillet(m, list(m.edges), 0.6, 8)
    assert isinstance(msg, str) and "too large" in msg
    # A lone edge (no faces).
    m.add_edge(QVector3D(5, 5, 5), QVector3D(6, 5, 5))
    lone = edge_at(m, (5, 5, 5), (6, 5, 5))
    assert isinstance(plan_fillet(m, [lone], 0.1), str)
    m.remove_edge(lone)
    # Four rounded edges at one vertex (a post on the corner).
    m.add_face([QVector3D(0, 0, 1), QVector3D(0, 0, 2), QVector3D(0, -1, 2), QVector3D(0, -1, 1)])
    m.add_face([QVector3D(0, 0, 1), QVector3D(1, 0, 1), QVector3D(1, 0, 2), QVector3D(0, 0, 2)])
    msg = plan_fillet(m, [edge_at(m, (0, 0, 1), (2, 0, 1)),
                          edge_at(m, (0, 0, 1), (0, 1, 1)),
                          edge_at(m, (0, 0, 1), (0, 0, 0)),
                          edge_at(m, (0, 0, 1), (0, 0, 2))], 0.1)
    assert isinstance(msg, str)
    assert isinstance(plan_fillet(m, [], 0.1), str)
    assert isinstance(plan_fillet(m, [edge_at(m, (2, 0, 1), (2, 1, 1))], 0.0), str)
    assert len(m.faces) == faces + 2 and len(m.edges) == edges + 7


def test_the_strip_inherits_a_material_shared_by_both_faces():
    m = box()
    for f in m.faces:
        f.attrs["color"] = (0.5, 0.2, 0.2)
    e = edge_at(m, (0, 0, 1), (2, 0, 1))
    plan = plan_fillet(m, [e], 0.2, 4)
    apply_fillet(m, plan)
    assert all(f.attrs.get("color") == (0.5, 0.2, 0.2) for f in m.faces)
    m = box()
    m.faces[1].attrs["color"] = (0.1, 0.9, 0.1)              # only the top
    plan = plan_fillet(m, [edge_at(m, (0, 0, 1), (2, 0, 1))], 0.2, 4)
    apply_fillet(m, plan)
    strips = m.faces[6:]
    assert all(not f.attrs for f in strips)
