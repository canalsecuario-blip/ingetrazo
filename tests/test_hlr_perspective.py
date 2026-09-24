"""The hidden-line drawing of a PERSPECTIVE view (File ▸ Export ▸ Current
view as DXF, after José Castro Basso's contribution): what hides in the
perspective is what hides, verticals stay vertical in two-point, and what
the view does not show is not drawn."""
from __future__ import annotations

import itertools
import math

import numpy as np
from PySide6.QtGui import QVector3D

from core.camera import OrbitCamera
from core.hlr import hlr_perspective


class _Scene:
    pass


def _cube(o=(0.0, 0.0, 0.0), s=2.0):
    o = np.asarray(o, dtype=float)
    v = np.array(list(itertools.product((0, 1), repeat=3)), float) * s + o
    quads = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6),
             (0, 2, 6, 4), (1, 5, 7, 3)]
    tris = [(v[a], v[b], v[c]) for a, b, c, d in quads] + \
        [(v[a], v[c], v[d]) for a, b, c, d in quads]
    edges = [(v[i], v[j]) for i, j in itertools.combinations(range(8), 2)
             if bin(i ^ j).count("1") == 1]
    return np.array(tris), np.array(edges)


def _geometry(*cubes):
    tris = np.concatenate([c[0] for c in cubes])
    hard = np.concatenate([c[1] for c in cubes])
    return tris, hard, np.empty((0, 2, 3)), np.empty((0, 2, 3))


def _cam(two_point=False):
    cam = OrbitCamera()
    cam.set_aspect(1600, 900)
    cam.target = QVector3D(1.0, 1.0, 1.0)
    cam.yaw, cam.pitch = math.radians(-60.0), math.radians(25.0)
    cam.distance = 12.0
    cam.two_point = two_point
    return cam


def _lengths(segs):
    return np.hypot(segs[:, 2] - segs[:, 0], segs[:, 3] - segs[:, 1])


def test_a_cube_shows_its_three_faces_nine_edges():
    segs = hlr_perspective(_Scene(), _cam(), geometry=_geometry(_cube()))
    # (the pass leaves 0.1 mm stubs at silhouette corners, parallel too)
    assert len(segs[_lengths(segs) > 1e-3]) == 9


def test_two_point_verticals_come_out_vertical():
    segs = hlr_perspective(_Scene(), _cam(two_point=True),
                           geometry=_geometry(_cube()))
    dx = np.abs(segs[:, 2] - segs[:, 0])
    dy = np.abs(segs[:, 3] - segs[:, 1])
    upright = (dy > 1e-3) & (dx < 1e-6)
    assert upright.sum() == 3                # the three visible verticals


def test_the_target_depth_is_true_size():
    cam = _cam(two_point=True)
    segs = hlr_perspective(_Scene(), cam, geometry=_geometry(_cube()))
    dy = np.abs(segs[:, 3] - segs[:, 1])
    # the verticals are 2 m; the one nearest the eye is drawn longest, the
    # farthest shortest, and the target sits between them
    assert dy.max() > 2.0 > dy[dy > 1e-3].min()


def test_what_is_behind_the_eye_is_not_drawn():
    cam = _cam()
    f = cam.forward()
    eye = cam.eye()
    behind = eye - f * 5.0
    alone = hlr_perspective(_Scene(), cam, geometry=_geometry(_cube()))
    both = hlr_perspective(
        _Scene(), cam,
        geometry=_geometry(_cube(), _cube((behind.x(), behind.y(),
                                           behind.z()))))
    assert len(both) == len(alone)
