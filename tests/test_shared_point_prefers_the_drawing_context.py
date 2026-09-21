# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""Issue #36 (@pacaeiro): a loose vertex and a component's corner at the
same coordinate — the loose one must win, whatever order the engine met
them in, because only it can be welded to (a line ended on the
component's copy closed no face)."""
from __future__ import annotations

from types import SimpleNamespace

from PySide6.QtGui import QVector3D

from core.snap import compute_snap


def V(x, y, z=0.0):
    return QVector3D(float(x), float(y), float(z))


def _w2p(p):
    return (p.x() * 100.0, p.y() * 100.0)


def _snap(edges, cand):
    return compute_snap(candidate_world=cand, candidate_pixel=_w2p(cand),
                        scene=SimpleNamespace(edges=edges), world_to_pixel=_w2p,
                        threshold_px=9.0, edge_threshold_px=14.0)


def test_the_loose_vertex_beats_the_components_corner_at_the_same_spot():
    comp = SimpleNamespace(a=V(2, 0), b=V(2, 2), context="component")
    loose = SimpleNamespace(a=V(0, 0), b=V(2, 0), context=None)
    for edges in ([comp, loose], [loose, comp]):          # either order
        r = _snap(edges, V(2.01, 0.01))
        assert r.kind == "endpoint" and r.context is None, edges


def test_a_component_corner_a_hair_closer_still_loses_the_tie():
    comp = SimpleNamespace(a=V(2.000001, 0), b=V(2, 2), context="component")
    loose = SimpleNamespace(a=V(0, 0), b=V(2, 0), context=None)
    r = _snap([comp, loose], V(2.000001, 0.0))
    assert r.context is None


def test_a_clearly_nearer_component_corner_wins_as_before():
    comp = SimpleNamespace(a=V(2, 0), b=V(2, 2), context="component")
    loose = SimpleNamespace(a=V(0, 0), b=V(2.05, 0), context=None)  # 5 px away
    r = _snap([loose, comp], V(2.0, 0.0))
    assert r.context == "component"
