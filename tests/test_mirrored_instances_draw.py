# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""A mirrored component placement draws instanced and shows its FRONT
(issue #158).

Mirrored placements used to leave the instanced pass — the mirror flips
the winding of every prototype triangle and GL would call the painted side
the back — and fell back to one baked world copy each. An industrial model
from @pacaeiro had 6 203 of them: 4.2 million faces baked one by one on the
first frame. They draw instanced now, in batches under a clockwise front
face. This renders both placements and reads the pixels: each shows its
front colour, not the back tint.

Needs a GL context that renders; skipped where the platform has none."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtGui import QMatrix4x4, QVector3D as V
from PySide6.QtWidgets import QApplication

_app = QApplication.instance() or QApplication([])

AMARILLO = (1.0, 0.85, 0.0)


def test_a_mirrored_placement_draws_instanced_with_its_front_colour():
    from core.group import Group
    from core.mesh import Mesh
    from views.main_window import MainWindow
    win = MainWindow()
    try:
        win.show()
        for _ in range(10):
            _app.processEvents()
        vp = win.viewport
        if getattr(vp, "_gl", None) is None or not vp.isValid():
            pytest.skip("no OpenGL context on this platform")
        sc = vp.scene
        sc.guides.clear()
        proto = Mesh()
        f = proto.add_face([V(-1, -1, 0), V(1, -1, 0), V(1, 1, 0), V(-1, 1, 0)])
        if f.normal().z() < 0:
            f.flip()
        f.attrs["color"] = list(AMARILLO)
        derecha, espejo = QMatrix4x4(), QMatrix4x4()
        derecha.translate(-2.0, 0.0, 0.0)
        espejo.translate(2.0, 0.0, 0.0)
        espejo.scale(-1.0, 1.0, 1.0)
        for m in (derecha, espejo):
            g = Group(proto, name="Pieza")
            g.xform = m
            sc.groups.append(g)
        sc.version += 1
        vp.camera.set_view("top")                     # looking down -Z: the front
        vp.camera.perspective = False
        vp.camera.fit_to(V(-4, -2, 0), V(4, 2, 0))
        for _ in range(5):
            _app.processEvents()
        img = vp.grabFramebuffer()
        lotes = getattr(vp, "_frame_instanced", {}) or {}
        assert any(k[2] for k in lotes), "the mirrored placement is instanced"
        assert not any(id(g) in getattr(vp, "_inst_chunks", {}) for g in sc.groups), \
            "and no placement was baked to world coordinates"
        dpr = img.width() / max(vp.width(), 1)
        for x in (-2.0, 2.0):
            px = vp._world_to_pixel(V(x, 0.5, 0))     # off the red axis
            c = img.pixelColor(int(px[0] * dpr), int(px[1] * dpr))
            r, g, b = c.redF(), c.greenF(), c.blueF()
            assert r > 0.6 and g > 0.5 and b < 0.35, (x, (r, g, b))
    finally:
        win._saved_version = win.viewport.scene.version
        win.close()


def _prisma(n=12, r=1.0, h=2.0):
    """A smooth n-sided prism: soft vertical edges, a curved side."""
    import math
    from core.mesh import Mesh
    m = Mesh()
    ring = [(r * math.cos(2 * math.pi * i / n), r * math.sin(2 * math.pi * i / n))
            for i in range(n)]
    for i in range(n):
        (x0, y0), (x1, y1) = ring[i], ring[(i + 1) % n]
        m.add_face([V(x0, y0, 0), V(x1, y1, 0), V(x1, y1, h), V(x0, y0, h)])
    for e in m.edges:
        if abs(e.a.z() - e.b.z()) > 1e-9:
            e.soft = True
    return m


def _baked_silhouette(vp, g, eye):
    import numpy as np
    ch = vp._group_chunk(g)
    e_np = np.array([eye.x(), eye.y(), eye.z()])
    s0 = np.einsum("ij,ij->i", ch["soft_n0"], ch["soft_c0"] - e_np)
    s1 = np.einsum("ij,ij->i", ch["soft_n1"], ch["soft_c1"] - e_np)
    mask = ch["soft_single"] | ((s0 < 0) != (s1 < 0))
    return ch["soft_pts"].reshape(-1, 6)[mask]


def test_a_placements_silhouette_in_local_space_matches_the_baked_one():
    """Same edges as baking the placement to world coordinates — rotated,
    mirrored and non-uniformly scaled — without baking it."""
    import numpy as np
    from core.group import Group
    from views.main_window import MainWindow
    win = MainWindow()
    try:
        vp = win.viewport
        proto = _prisma()
        mats = []
        for sx, ang, sz in ((1, 0, 1), (-1, 30, 1), (1, 75, 2.5), (-1, 200, 0.4)):
            m = QMatrix4x4()
            m.translate(3.0 * len(mats), 1.0, 0.5)
            m.rotate(ang, 0.3, 0.2, 1.0)
            m.scale(sx, 1.3, sz)
            mats.append(m)
        gs = []
        for m in mats:
            g = Group(proto, name="Columna")
            g.xform = m
            vp.scene.groups.append(g)
            gs.append(g)
        vp.scene.version += 1
        for eye in (V(20, -15, 8), V(-6, 9, 3), V(4, 1, 30)):
            for g in gs:
                got = np.frombuffer(vp._instance_silhouette(g, eye, None),
                                    np.float32).reshape(-1, 6)
                ref = _baked_silhouette(vp, g, eye)
                assert len(got) == len(ref) > 0
                key = lambda a: sorted(map(tuple, np.round(a, 3)))
                assert key(got) == key(ref)
    finally:
        win._saved_version = win.viewport.scene.version
        win.close()
