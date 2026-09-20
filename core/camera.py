# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""Orbital camera for the 3D viewport.

Z-up convention (SketchUp, Blender, FreeCAD): X red (east), Y green (north),
Z blue (up). The camera orbits around a ``target`` point in spherical
coordinates (``yaw``, ``pitch``, ``distance``). Both perspective and parallel
("orthographic") projections are supported.
"""
from __future__ import annotations

import math

from PySide6.QtGui import QMatrix4x4, QVector3D


#: How close the camera may get to what it is looking at. A component is
#: centimetres, not metres: half a metre away is as close as you can stand
#: to a wall, and it left the face of a figure or the rim of a wheel
#: impossible to look at. Two centimetres is close enough for any of it.
MIN_DISTANCE = 0.02

#: Ceiling: past this the model is a dot and the depth buffer is noise.
MAX_DISTANCE = 10000.0


class OrbitCamera:
    """Camera that orbits around a target point."""

    def __init__(self) -> None:
        self.target = QVector3D(0.0, 0.0, 0.0)
        self.distance = 20.0
        self.yaw = math.radians(-45.0)
        self.pitch = math.radians(30.0)
        self.up = QVector3D(0.0, 0.0, 1.0)
        self.fov_deg = 45.0
        self.aspect = 1.0
        self.znear = 0.1
        self.zfar = 10000.0
        self.perspective = True

    # ---- Derived state ------------------------------------------------------
    def eye(self) -> QVector3D:
        cp = math.cos(self.pitch)
        sp = math.sin(self.pitch)
        cy = math.cos(self.yaw)
        sy = math.sin(self.yaw)
        return self.target + QVector3D(
            self.distance * cp * cy,
            self.distance * cp * sy,
            self.distance * sp,
        )

    def forward(self) -> QVector3D:
        """Unit view direction, eye → target."""
        d = self.target - self.eye()
        return d.normalized() if d.lengthSquared() > 1e-18 else QVector3D(0, 1, 0)

    def up_vector(self) -> QVector3D:
        """The up vector every projection must use: ``up`` itself, unless
        the sight line runs along it — the exact Top and Bottom views —
        where ``lookAt`` has no right and a cross product gives nothing.
        There it is the limit of the view a hair short of vertical: north
        up the screen in Top (y+ at the default yaw), the same axis the
        other way in Bottom, so the exact view looks like the 89° one it
        replaces, only straight. A rolled ``up`` (the composer turning a
        plan) is never along the sight line and comes back as it is."""
        f = self.forward()
        if abs(QVector3D.dotProduct(f, self.up)) < 0.9999:
            return self.up
        sign = -1.0 if self.pitch > 0 else 1.0
        return QVector3D(sign * math.cos(self.yaw), sign * math.sin(self.yaw),
                         0.0)

    # ---- First person (SketchUp's Position Camera / Look Around / Walk) -----
    # The orbit model stays: a walkthrough only ever asks "the eye is HERE,
    # looking THERE", and that is a target at ``distance`` along the look
    # direction. Nothing else in the viewport has to learn a second camera.

    def look_from(self, eye: QVector3D, direction: QVector3D) -> None:
        """Put the eye at ``eye`` looking along ``direction`` (any length).
        A near-vertical look keeps just off the pole, like ``orbit``."""
        d = QVector3D(direction)
        if d.lengthSquared() < 1e-18:
            d = self.forward()
        d = d.normalized()
        # eye = target + distance·(cp·cy, cp·sy, sp): the eye sits BEHIND
        # the target along -forward, so the spherical angles come from -d.
        pitch = math.asin(max(-1.0, min(1.0, -d.z())))
        pitch = max(min(pitch, math.radians(89.0)), math.radians(-89.0))
        if abs(math.cos(pitch)) > 1e-9:
            yaw = math.atan2(-d.y(), -d.x())
        else:
            yaw = self.yaw
        self.yaw, self.pitch = yaw, pitch
        self.target = eye + d * self.distance

    def turn(self, d_yaw_deg: float, d_pitch_deg: float) -> None:
        """Turn the head: the eye stays put, the look direction swings by
        ``d_yaw_deg`` to the right (clockwise seen from above) and
        ``d_pitch_deg`` upward."""
        eye = self.eye()
        d = self.forward()
        yaw = math.atan2(d.y(), d.x()) - math.radians(d_yaw_deg)
        pitch = math.asin(max(-1.0, min(1.0, d.z()))) + math.radians(d_pitch_deg)
        pitch = max(min(pitch, math.radians(89.0)), math.radians(-89.0))
        cp = math.cos(pitch)
        self.look_from(eye, QVector3D(cp * math.cos(yaw), cp * math.sin(yaw),
                                      math.sin(pitch)))

    def move_eye(self, delta: QVector3D) -> None:
        """Walk: eye and target move together, the look stays the same."""
        self.target = self.target + delta

    def view_matrix(self) -> QMatrix4x4:
        m = QMatrix4x4()
        m.lookAt(self.eye(), self.target, self.up_vector())
        return m

    def projection_matrix(self) -> QMatrix4x4:
        m = QMatrix4x4()
        if self.perspective:
            # The near plane follows the camera in: at any normal working
            # distance it is the usual 0.1 m, and only when you come right up
            # to something does it step back out of the way — otherwise the
            # near plane itself is what stops you.
            near = min(self.znear, max(self.distance * 0.02, 1e-4))
            m.perspective(self.fov_deg, self.aspect, near, self.zfar)
        else:
            # Parallel projection — size derived from camera distance so the
            # framing matches what the user sees in perspective.
            half_h = self.distance * math.tan(math.radians(self.fov_deg) / 2.0)
            half_w = half_h * self.aspect
            m.ortho(-half_w, half_w, -half_h, half_h, -self.zfar, self.zfar)
        return m

    # ---- Navigation ---------------------------------------------------------
    def orbit(self, dx_pixels: float, dy_pixels: float, viewport_h: int) -> None:
        """Turn the model under the cursor, SketchUp/Blender style.

        Both axes GRAB THE MODEL: drag right and the model swings right,
        drag down and it tips down — you come up over it and see its top.
        Same gesture as :meth:`pan`, and that is the check that matters,
        because until 2026-09-09 the vertical axis disagreed with it:
        ``pitch`` went the other way, so dragging down moved the CAMERA
        down and the model appeared to slide up while the horizontal axis
        kept grabbing. Two users reported it the same day (GitHub #7 and
        an e-mail), neither able to say which of the two axes was wrong —
        which is exactly what a single inverted axis feels like from the
        outside.

        Callers that let the user ask for the old feel negate ``dy_pixels``
        (Preferences ▸ Invert vertical orbit); the convention itself lives
        here.
        """
        scale = math.pi / max(viewport_h, 1)
        self.yaw -= dx_pixels * scale
        # Clamp to just shy of poles to avoid the up-vector singularity.
        self.pitch = max(
            min(self.pitch + dy_pixels * scale, math.radians(89.0)),
            math.radians(-89.0),
        )

    def pan(self, dx_pixels: float, dy_pixels: float, viewport_h: int) -> None:
        cp = math.cos(self.pitch)
        sp = math.sin(self.pitch)
        cy = math.cos(self.yaw)
        sy = math.sin(self.yaw)
        # View direction (eye → target): the eye sits at
        # target + distance·(cp·cy, cp·sy, sp), so forward is its negation.
        # Using +that vector flipped screen-right, inverting horizontal pan.
        forward = QVector3D(-cp * cy, -cp * sy, -sp)
        right = QVector3D.crossProduct(forward, self.up_vector()).normalized()
        screen_up = QVector3D.crossProduct(right, forward).normalized()
        world_per_pixel = (
            2.0
            * self.distance
            * math.tan(math.radians(self.fov_deg) / 2.0)
            / max(viewport_h, 1)
        )
        self.target = self.target - right * (dx_pixels * world_per_pixel)
        self.target = self.target + screen_up * (dy_pixels * world_per_pixel)

    def zoom(self, steps: float) -> None:
        factor = 0.9 ** steps
        self.distance = max(MIN_DISTANCE,
                            min(self.distance * factor, MAX_DISTANCE))

    def zoom_to(self, steps: float, focus: QVector3D,
                min_step: float = 0.0) -> None:
        """Zoom keeping the world point ``focus`` (under the cursor) fixed on
        screen, SketchUp-style. The whole frame scales toward ``focus``, so both
        the distance and the target move by the same factor.

        Two escapes from the "stuck" close-up (the orbit distance pinned at
        MIN_DISTANCE, 2 cm): zooming IN keeps sliding the target toward the
        focus even when the distance cannot shrink any more, and zooming OUT
        retreats the eye by at least ``min_step`` (the viewport passes ~1 %
        of the model's size) — at 2 cm a plain 10 % step was 2 mm per
        notch, dozens of notches to see anything, so users reached for Zoom
        Extents instead."""
        factor = 0.9 ** steps
        new_distance = max(MIN_DISTANCE,
                           min(self.distance * factor, MAX_DISTANCE))
        eye_before = self.eye()
        self.target = focus + (self.target - focus) * factor
        self.distance = new_distance
        if steps < 0 and min_step > 0.0:
            moved = (self.eye() - eye_before).length()
            if moved < min_step:
                back = self.eye() - self.target
                if back.length() > 1e-9:
                    self.target += back.normalized() * (min_step - moved)

    def set_aspect(self, w: int, h: int) -> None:
        self.aspect = max(w, 1) / max(h, 1)

    def toggle_projection(self) -> None:
        self.perspective = not self.perspective

    # ---- Navigation presets ------------------------------------------------
    def fit_to(self, min_pt: QVector3D, max_pt: QVector3D, margin: float = 1.3) -> None:
        """Center the camera on the AABB and back up enough to frame it."""
        center = QVector3D(
            (min_pt.x() + max_pt.x()) * 0.5,
            (min_pt.y() + max_pt.y()) * 0.5,
            (min_pt.z() + max_pt.z()) * 0.5,
        )
        diag = (max_pt - min_pt).length()
        if diag < MIN_DISTANCE:
            diag = MIN_DISTANCE      # an empty scene still needs a distance
        self.target = center
        fov_rad = math.radians(self.fov_deg)
        self.distance = max(diag * margin / (2.0 * math.tan(fov_rad / 2.0)),
                            MIN_DISTANCE)

    # Yaw / pitch presets for standard architectural views (Z-up convention).
    # Top and Bottom are EXACTLY vertical: at 89° the parallel projection
    # showed every vertical edge as a short line and a plan came out a
    # hair oblique (@pacaeiro, issue #45: «Top and Bottom views are not
    # straight (camera not perpendicular to view)»). ``up_vector`` keeps
    # lookAt and the camera bases from degenerating there.
    _STANDARD_VIEWS = {
        "top":    (math.radians(-90.0), math.radians(90.0)),
        "bottom": (math.radians(-90.0), math.radians(-90.0)),
        "front":  (math.radians(-90.0), 0.0),
        "back":   (math.radians(90.0), 0.0),
        "right":  (0.0, 0.0),
        "left":   (math.radians(180.0), 0.0),
        "iso":    (math.radians(-45.0), math.radians(30.0)),
    }

    def set_view(self, name: str) -> None:
        preset = self._STANDARD_VIEWS.get(name)
        if preset is None:
            return
        self.yaw, self.pitch = preset
