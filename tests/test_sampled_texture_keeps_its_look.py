# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""A texture positioned with the pins, sampled with the eyedropper and
painted on a face of ANOTHER plane keeps its look — the tile size and the
turn — as that face's planar projection (Marco, 2026-09-15: «debería poder
copiar esa muestra… y aplicarlo a otra cara»). Coplanar faces keep the
map itself, as before."""
from __future__ import annotations

import pytest
from PySide6.QtGui import QVector3D

from core.mesh import Mesh
from core.texture import face_uv_axes, flattened_texture, placement_of
from tools.paint import _face_plane, _texture_commands


def _floor_and_wall():
    m = Mesh()
    floor = m.add_face([QVector3D(0, 0, 0), QVector3D(2, 0, 0),
                        QVector3D(2, 2, 0), QVector3D(0, 2, 0)])
    if floor.normal().z() < 0:
        floor.loop.reverse()
    wall = m.add_face([QVector3D(0, 0, 0), QVector3D(0, 0, 2),
                       QVector3D(2, 0, 2), QVector3D(2, 0, 0)])
    return m, floor, wall


def _positioned(sw=0.5, sh=0.5, scale=2.0, rot_deg=90.0):
    """The map the pins leave on a +Z floor: tiles ``sw``×``sh`` scaled by
    ``scale`` and turned by ``rot_deg`` about the red pin at the origin."""
    import math
    a = math.radians(rot_deg)
    e_u = QVector3D(math.cos(a), math.sin(a), 0) * (sw * scale)
    e_v = QVector3D(-math.sin(a), math.cos(a), 0) * (sh * scale)
    from tools.texture_position import TextureMap
    return {"path": "brick.png", "sw": sw, "sh": sh,
            "uvw": TextureMap(QVector3D(), (0.0, 0.0), e_u, e_v).uvw()}


def test_placement_reads_scale_and_turn_off_the_map():
    tex = _positioned()
    sw, sh, rot = placement_of(tex, QVector3D(0, 0, 1))
    assert sw == pytest.approx(1.0) and sh == pytest.approx(1.0)
    assert rot == pytest.approx(90.0)
    flat = flattened_texture(tex, QVector3D(0, 0, 1))
    assert "uvw" not in flat and flat["sw"] == pytest.approx(1.0)
    assert flat["rot"] == pytest.approx(90.0)
    # No map: nothing to read.
    assert placement_of({"path": "x.png"}, QVector3D(0, 0, 1)) is None
    assert flattened_texture({"path": "x.png", "sw": 0.3}, QVector3D(0, 0, 1)) \
        == {"path": "x.png", "sw": 0.3}


def test_painting_another_plane_keeps_the_look_and_the_same_plane_the_map():
    m, floor, wall = _floor_and_wall()
    tex = _positioned()
    floor.attrs["texture"] = dict(tex)
    plane = _face_plane(floor)

    class _Scene:
        mesh = m
        version = 0
        materials = {}
        groups = []
    scene = _Scene()
    for cmd in _texture_commands([wall], tex, plane):
        cmd.do(scene)
    got = wall.attrs["texture"]
    assert "uvw" not in got
    assert got["sw"] == pytest.approx(1.0) and got["sh"] == pytest.approx(1.0)
    assert got["rot"] == pytest.approx(90.0)
    # The wall tiles at 1 m: one tile per metre along its own U axis.
    gu, cu, gv, cv = face_uv_axes(got, wall.normal())
    assert gu.length() == pytest.approx(1.0) and gv.length() == pytest.approx(1.0)
    # A second floor face keeps the very map.
    other = m.add_face([QVector3D(2, 0, 0), QVector3D(4, 0, 0),
                        QVector3D(4, 2, 0), QVector3D(2, 2, 0)])
    if other.normal().z() < 0:
        other.loop.reverse()
    for cmd in _texture_commands([other], tex, plane):
        cmd.do(scene)
    assert other.attrs["texture"]["uvw"] == tex["uvw"]
