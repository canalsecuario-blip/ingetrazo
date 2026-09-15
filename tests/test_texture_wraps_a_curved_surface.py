# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""Painting a curved surface wraps the texture around it (Marco's rounded
corner, 2026-09-15: «la textura en esa curva se ve rara»). Each facet used
to get its own planar projection, so the bricks restarted — shifted, cut —
on every facet. Now the image is laid on the clicked facet and carried
across every soft edge by the hinge rotation, so the seam between two
facets reads the same UV from both sides: the pattern continues."""
from __future__ import annotations

import math

import pytest
from PySide6.QtGui import QVector3D

from core.mesh import Mesh
from core.texture import continuous_maps, face_uv_axes
from tools.paint import _face_plane, _surface_commands

TEX = {"path": "brick.png", "sw": 0.5, "sh": 0.5}


def _quarter_cylinder(segments=6, r=1.0, h=1.0):
    """The side of a rounded corner: vertical facets around a quarter
    circle, joined by soft edges."""
    m = Mesh()
    faces = []
    for k in range(segments):
        a0 = math.pi / 2 * k / segments
        a1 = math.pi / 2 * (k + 1) / segments
        p0 = QVector3D(r * math.cos(a0), r * math.sin(a0), 0)
        p1 = QVector3D(r * math.cos(a1), r * math.sin(a1), 0)
        faces.append(m.add_face([p0, p1, QVector3D(p1.x(), p1.y(), h),
                                 QVector3D(p0.x(), p0.y(), h)]))
    for e in m.edges:
        if abs(e.a.z() - e.b.z()) > 1e-9 and 0 < e.a.x() < r - 1e-9:
            e.soft = True                       # the vertical seams
    assert len(m.surface_of(faces[0])) == segments
    return m, faces


def _uv(tex, face, p):
    gu, cu, gv, cv = face_uv_axes(tex, face.normal())
    return (QVector3D.dotProduct(gu, p) + cu, QVector3D.dotProduct(gv, p) + cv)


def test_the_seams_read_the_same_uv_from_both_facets():
    m, faces = _quarter_cylinder()
    maps = continuous_maps(m, faces, faces[0], TEX)
    assert len(maps) == len(faces)
    for a, b in zip(faces, faces[1:]):
        shared = [p for p in a.vertices if any((p - q).length() < 1e-9 for q in b.vertices)]
        assert len(shared) == 2
        for p in shared:
            ua = _uv(maps[id(a)], a, p)
            ub = _uv(maps[id(b)], b, p)
            assert ua == pytest.approx(ub, abs=1e-6)
    # The seed keeps its planar projection; the image is not stretched:
    # one tile still spans 0.5 m along every facet.
    for f in faces:
        gu, _cu, gv, _cv = face_uv_axes(maps[id(f)], f.normal())
        assert gu.length() == pytest.approx(2.0, abs=1e-6)
        assert gv.length() == pytest.approx(2.0, abs=1e-6)
        assert abs(QVector3D.dotProduct(gu, f.normal().normalized())) < 1e-6


def test_a_planar_projection_would_have_cut_the_pattern():
    """The old behaviour, for contrast: planar per facet disagrees at the seam."""
    m, faces = _quarter_cylinder()
    a, b = faces[2], faces[3]
    shared = [p for p in a.vertices if any((p - q).length() < 1e-9 for q in b.vertices)]
    ua = _uv(TEX, a, shared[0])
    ub = _uv(TEX, b, shared[0])
    assert ua != pytest.approx(ub, abs=1e-3)


def test_the_paint_tool_wraps_the_surface_from_the_clicked_facet():
    m, faces = _quarter_cylinder()

    class _Scene:
        mesh = m
        version = 0
        materials = {}
        groups = []
    cmds = _surface_commands(m, faces, faces[3], TEX, None)
    assert cmds is not None and len(cmds) == len(faces)
    for c in cmds:
        c.do(_Scene())
    assert all(f.attrs["texture"].get("uvw") for f in faces)
    # A single flat face is not a surface: the ordinary rule applies.
    assert _surface_commands(m, [faces[0]], faces[0], TEX, None) is None
    # A positioned sample from another plane wraps with its LOOK.
    from tools.texture_position import TextureMap
    tex = {"path": "brick.png", "sw": 0.5, "sh": 0.5,
           "uvw": TextureMap(QVector3D(), (0.0, 0.0), QVector3D(1, 0, 0),
                             QVector3D(0, 1, 0)).uvw()}
    floor = m.add_face([QVector3D(5, 5, 0), QVector3D(6, 5, 0),
                        QVector3D(6, 6, 0), QVector3D(5, 6, 0)])
    cmds = _surface_commands(m, faces, faces[0], tex, _face_plane(floor))
    for c in cmds:
        c.do(_Scene())
    gu, _cu, gv, _cv = face_uv_axes(faces[0].attrs["texture"], faces[0].normal())
    assert gu.length() == pytest.approx(1.0, abs=1e-6)       # 1 m tiles now


def test_a_selected_surface_wraps_too_and_the_rest_of_the_selection_does_not():
    """Select the surface (a click selects it whole), paint it: the soft-joined
    facets wrap from the clicked one; a flat face in the same selection,
    joined by nothing soft, takes the ordinary planar projection."""
    m, faces = _quarter_cylinder()
    flat = m.add_face([QVector3D(5, 5, 0), QVector3D(6, 5, 0),
                       QVector3D(6, 6, 0), QVector3D(5, 6, 0)])

    class _Scene:
        mesh = m
        version = 0
        materials = {}
        groups = []
    cmds = _surface_commands(m, faces + [flat], faces[2], TEX, None)
    assert cmds is not None
    for c in cmds:
        c.do(_Scene())
    assert all(f.attrs["texture"].get("uvw") for f in faces)
    assert "uvw" not in flat.attrs["texture"]
    for a, b in zip(faces, faces[1:]):
        shared = [p for p in a.vertices if any((p - q).length() < 1e-9 for q in b.vertices)]
        for p in shared:
            assert _uv(a.attrs["texture"], a, p) == pytest.approx(
                _uv(b.attrs["texture"], b, p), abs=1e-6)
