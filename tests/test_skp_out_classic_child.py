# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""Export ▸ SketchUp must survive a CLASSIC group nested in a container.

A group that owns its geometry has no ``xform``: its mesh is already in the
coordinates its parent expects — that is what "classic" means, as opposed
to an instance, which is a shared prototype plus a matrix. ``_placement``
handed that ``None`` straight to ``_instance_placement``, which reads rows
off it, so exporting a container with such a child died with
``AttributeError: 'NoneType' object has no attribute 'row'``.

Found on 2026-09-17 exporting Marco's own Plaza Yanque to .skp — «Group 8»,
a classic group with a mesh, sitting inside a container. His flagship model
could not be exported to SketchUp at all.

For a classic child the right placement is the IDENTITY: there is nothing
to transform, the geometry is where it says it is.
"""
from __future__ import annotations

import pytest
from PySide6.QtGui import QMatrix4x4, QVector3D

from core.group import Group
from core.mesh import Mesh
from formats.skp_out import _instance_placement, _placement

V = QVector3D


def _square(z=0.0):
    m = Mesh()
    m.add_face([V(0, 0, z), V(1, 0, z), V(1, 1, z), V(0, 1, z)])
    return m


def test_a_classic_group_places_at_the_identity():
    """No transform means no transform — not a crash."""
    g = Group(name="Group 8", mesh=_square())
    assert getattr(g, "xform", None) is None      # this is what classic means
    translation, matrix3x3 = _placement({"name": "Group 8"}, g)
    assert translation == (0.0, 0.0, 0.0)
    assert matrix3x3 == (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0)


def test_the_helper_itself_takes_none_as_the_identity():
    assert _instance_placement(None) == (
        (0.0, 0.0, 0.0), (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0))


def test_an_instance_still_places_by_its_matrix():
    """The path that already worked, pinned so the fix cannot flatten it."""
    x = QMatrix4x4()
    x.translate(2.0, 3.0, 4.0)
    g = Group(name="Inst", mesh=_square())
    g.xform = x
    translation, matrix3x3 = _placement({"name": "Inst"}, g)
    # metres → inches on the translation, the 3×3 untouched
    assert translation == pytest.approx((2.0 / 0.0254, 3.0 / 0.0254,
                                         4.0 / 0.0254))
    assert matrix3x3 == (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0)


def test_a_billboard_still_places_at_its_anchor():
    """The other branch of _placement, untouched."""
    g = Group(name="Sumari", mesh=_square())
    entry = {"name": "Sumari", "billboard": True, "anchor": V(1.0, 0.0, 0.0)}
    translation, matrix3x3 = _placement(entry, g)
    assert translation == pytest.approx((1.0 / 0.0254, 0.0, 0.0))
    assert matrix3x3 == (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0)
