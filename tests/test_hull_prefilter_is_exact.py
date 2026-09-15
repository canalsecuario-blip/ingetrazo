# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""The group box's 2D hull prefilter (dedupe + sixteen extreme directions)
must give the same hull as a plain monotone chain — it only drops points
that cannot be hull vertices. On the Plaza Yanque the old four-extreme
test let ~100k points reach the Python scan: 350 ms per box, paid on
every edit inside the container (Marco, 2026-09-14)."""
import numpy as np

from core.group import _hull_2d


def _plain_hull(pts):
    p = pts[np.lexsort((pts[:, 1], pts[:, 0]))]

    def half(seq):
        out = []
        for q in seq:
            while len(out) >= 2:
                a, b = out[-2], out[-1]
                if (b[0] - a[0]) * (q[1] - a[1]) - (b[1] - a[1]) * (q[0] - a[0]) > 0:
                    break
                out.pop()
            out.append(q)
        return out
    lower, upper = half(p), half(p[::-1])
    return np.array(lower[:-1] + upper[:-1])


def _same_polygon(a, b):
    if len(a) != len(b):
        return False
    b2 = np.concatenate([b, b])
    for k in range(len(b)):
        if np.allclose(a, b2[k:k + len(a)]):
            return True
    return False


def test_hull_matches_the_plain_monotone_chain_on_awkward_sets():
    rng = np.random.default_rng(7)
    sets = [
        rng.uniform(-50, 50, (5000, 2)),                                  # a cloud
        np.concatenate([rng.uniform(0, 100, (4000, 2)),
                        np.repeat(rng.uniform(0, 100, (50, 2)), 20, 0)]),  # duplicates
    ]
    # A rectangular site with slightly bowed edges (the plaza): points along
    # the perimeter bulge outside the four-extreme quadrilateral.
    t = np.linspace(0, 1, 3000)
    top = np.stack([t * 120, 80 + 0.3 * np.sin(np.pi * t)], 1)
    bottom = np.stack([t * 120, -0.3 * np.sin(np.pi * t)], 1)
    left = np.stack([-0.3 * np.sin(np.pi * t), t * 80], 1)
    right = np.stack([120 + 0.3 * np.sin(np.pi * t), t * 80], 1)
    sets.append(np.concatenate([top, bottom, left, right, rng.uniform(0, 100, (3000, 2))]))
    for pts in sets:
        assert _same_polygon(_hull_2d(pts), _plain_hull(np.unique(pts, axis=0)))


def test_the_containers_box_reuses_the_prototypes_point_arrays(tmp_path):
    """The container's box asked placement_points to rebuild every
    prototype's array on every scene version (73 ms on the plaza); the
    viewport now keeps them per chunk revision — reused while the
    prototype is untouched, rebuilt when its mesh changes."""
    import os
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    from PySide6.QtGui import QMatrix4x4, QVector3D
    from PySide6.QtWidgets import QApplication
    QApplication.instance() or QApplication([])
    from views.viewport import Viewport
    from core.group import Group
    from core.mesh import Mesh
    vp = Viewport(None)
    proto = Mesh()
    proto.add_face([QVector3D(0, 0, 0), QVector3D(1, 0, 0), QVector3D(1, 1, 0), QVector3D(0, 1, 0)])
    kids = []
    for i in range(3):
        g = Group(proto, f"copia {i}")
        m = QMatrix4x4()
        m.translate(3 * i, 0, 0)
        g.xform = m
        kids.append(g)
    cont = Group(Mesh(), "contenedor")
    cont.xform = QMatrix4x4()
    cont.children = kids
    vp.scene.groups.append(cont)
    vp.scene.version += 1
    vp._group_obb(cont)
    arr1 = vp._proto_pts_store[id(proto)][1]
    kids[1].xform.translate(0, 5, 0)
    vp.scene.version += 1                                   # a child moved: new box…
    frame, lo, hi = vp._group_obb(cont)
    assert vp._proto_pts_store[id(proto)][1] is arr1        # …same prototype array
    assert hi[1] - lo[1] > 5.5
    v = proto.vertices[0]
    v.position = QVector3D(-2, 0, 0)                        # the prototype itself edited
    proto._mut_serial += 1                                  # (what a mutation primitive does)
    vp.scene.version += 1
    vp._group_obb(cont)
    assert vp._proto_pts_store[id(proto)][1] is not arr1    # rebuilt
