# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""The DRAWING AXES: the one red/green/blue every tool and inference reads.

At the top level they are the world's. Inside a group or component they are
that context's own axes (issue #44, @pacaeiro; SketchUp: «when you open a
group for editing you see its axes, not the model axes» — inferences,
arrow-key locks, the rectangle, the ground plane and the standard views all
follow them, level by level).

``AXES`` is ONE dict object, updated in place: ``core.snap._AXIS_VECTORS``,
``tools.base.PLANE_LOCK_AXES`` and the tools' own tables are the same
object, so a context switch reaches every one of them at once and nothing
can keep a stale copy. With the world frame the vectors are exactly
(1,0,0), (0,1,0), (0,0,1) — bit for bit what those tables held before, which
is what lets the snap harness prove the top level did not move.

The viewport calls :func:`sync` with ``scene.drawing_frame`` before it asks
the engine anything.
"""
from __future__ import annotations

from PySide6.QtGui import QVector3D

_WORLD = {"x": (1.0, 0.0, 0.0), "y": (0.0, 1.0, 0.0), "z": (0.0, 0.0, 1.0)}

#: The current red, green and blue, as unit vectors (updated in place).
AXES: dict = {k: QVector3D(*v) for k, v in _WORLD.items()}
#: Where they meet.
ORIGIN = QVector3D(0.0, 0.0, 0.0)

_current = None          # the matrix last synced (identity check), or None


def is_world() -> bool:
    return _current is None


def origin() -> QVector3D:
    return QVector3D(ORIGIN)


def axis(name: str) -> QVector3D:
    return QVector3D(AXES[name])


def as_tuple(name: str) -> tuple:
    v = AXES[name]
    return (v.x(), v.y(), v.z())


def sync(frame) -> None:
    """Make the drawing axes ``frame``'s (a world matrix, see
    ``Scene.drawing_frame``), or the world's for ``None``. Cheap when
    nothing changed — it runs on every mouse move."""
    global _current
    if frame is _current or (frame is not None and _current is not None
                             and frame == _current):
        return
    if frame is None:
        for k, v in _WORLD.items():
            AXES[k] = QVector3D(*v)
        ORIGIN.setX(0.0)
        ORIGIN.setY(0.0)
        ORIGIN.setZ(0.0)
        _current = None
        return
    from core.group import frame_axes
    o, x, y, z = frame_axes(frame)
    AXES["x"], AXES["y"], AXES["z"] = x, y, z
    ORIGIN.setX(o.x())
    ORIGIN.setY(o.y())
    ORIGIN.setZ(o.z())
    from PySide6.QtGui import QMatrix4x4
    _current = QMatrix4x4(frame)


def to_local(v: QVector3D) -> QVector3D:
    """A world DIRECTION in drawing-axes components."""
    return QVector3D(QVector3D.dotProduct(v, AXES["x"]),
                     QVector3D.dotProduct(v, AXES["y"]),
                     QVector3D.dotProduct(v, AXES["z"]))


def to_world(v: QVector3D) -> QVector3D:
    """Drawing-axes components back to a world direction."""
    return AXES["x"] * v.x() + AXES["y"] * v.y() + AXES["z"] * v.z()


def plane_axes(normal: QVector3D) -> tuple[QVector3D, QVector3D]:
    """``core.triangulate.plane_axes`` for DRAWING: the in-plane ``u`` is
    the drawing red projected (green when the plane faces red), so a
    rectangle or a circle inside a turned group lines up with the group.
    At the top level it IS the original — texture, topology and hidden-line
    code keep calling that one directly, in world terms."""
    from core.triangulate import plane_axes as world_plane_axes
    if is_world():
        return world_plane_axes(normal)
    n = normal.normalized()
    ref = QVector3D(AXES["x"])
    u = ref - n * QVector3D.dotProduct(ref, n)
    if u.length() < 0.1:
        ref = QVector3D(AXES["y"])
        u = ref - n * QVector3D.dotProduct(ref, n)
    u = u.normalized()
    v = QVector3D.crossProduct(n, u).normalized()
    return u, v


def frame_matrix(o: QVector3D, x: QVector3D, y: QVector3D,
                 z: QVector3D):
    """The world matrix whose columns are ``x``, ``y``, ``z`` and whose
    translation is ``o`` — a frame back into matrix form."""
    from PySide6.QtGui import QMatrix4x4
    return QMatrix4x4(x.x(), y.x(), z.x(), o.x(),
                      x.y(), y.y(), z.y(), o.y(),
                      x.z(), y.z(), z.z(), o.z(),
                      0.0, 0.0, 0.0, 1.0)
