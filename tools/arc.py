# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""Arc tool: two endpoints (the chord), then a bulge.

SketchUp's 2-point arc:
1. click the start point,
2. click the end point — the chord,
3. move to bulge the arc out from the chord, click to commit.

The arc is committed as a polyline of short edges (it auto-faces if it closes a
region with existing geometry). The bulge can be typed in the VCB.
"""
from __future__ import annotations

import math

from core.i18n import tr

from PySide6.QtGui import QVector3D

from core.edits import build_add_edges
from core.history import RebuildPlanarFacesCommand, TagCurveCommand
from core.triangulate import plane_axes
from tools.base import PlaneLock, Tool, ToolContext

_SEGMENTS = 16  # polyline segments approximating the arc


def _circumcenter2(a, b, c):
    ax, ay = a
    bx, by = b
    cx, cy = c
    d = 2.0 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(d) < 1e-12:
        return None
    a2, b2, c2 = ax * ax + ay * ay, bx * bx + by * by, cx * cx + cy * cy
    ux = (a2 * (by - cy) + b2 * (cy - ay) + c2 * (ay - by)) / d
    uy = (a2 * (cx - bx) + b2 * (ax - cx) + c2 * (bx - ax)) / d
    return (ux, uy)


def _wrap(a: float) -> float:
    while a <= -math.pi:
        a += 2.0 * math.pi
    while a > math.pi:
        a -= 2.0 * math.pi
    return a


def _arc_3pts_2d(s, m, e, segments):
    """2D points of the circular arc from ``s`` to ``e`` passing through ``m``
    (the circumcircle of the three), sampled into ``segments`` spans. Falls back
    to the straight chord when the three points are collinear."""
    center = _circumcenter2(s, m, e)
    if center is None:
        return [s, e]
    cx, cy = center
    r = math.hypot(s[0] - cx, s[1] - cy)
    a0 = math.atan2(s[1] - cy, s[0] - cx)
    a1 = math.atan2(e[1] - cy, e[0] - cx)
    am = math.atan2(m[1] - cy, m[0] - cx)
    d = _wrap(a1 - a0)
    da = _wrap(am - a0)
    if d >= 0 and not (0.0 <= da <= d):
        d -= 2.0 * math.pi
    elif d < 0 and not (d <= da <= 0.0):
        d += 2.0 * math.pi
    return [(cx + r * math.cos(a0 + d * (k / segments)),
             cy + r * math.sin(a0 + d * (k / segments)))
            for k in range(segments + 1)]




def commit_arc(viewport, pts: list[QVector3D], close_to=None) -> None:
    """Commit an arc polyline with the shared curve pipeline: planar
    arrangement on flat drawings, scoped per-plane arrangement when the
    drawing plane already carries content in a 3D scene, naive otherwise.
    Used by every arc variant. With ``close_to`` (a centre point) the two
    radius edges close the wedge — SketchUp's Pie."""
    segments = [(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]
    if close_to is not None:
        segments = ([(close_to, pts[0])] + segments
                    + [(pts[-1], close_to)])
    from tools.circle import busy_plane, flat_drawing
    if flat_drawing(viewport.scene, pts):
        cmd = build_add_edges(
            viewport.scene, segments, detect_faces=False,
            extra=[TagCurveCommand(list(pts), closed=False),
                   RebuildPlanarFacesCommand()])
    elif (plane := busy_plane(viewport.scene, pts)) is not None:
        from core.history import RebuildPlaneFacesCommand
        cmd = build_add_edges(
            viewport.scene, segments, detect_faces=True,
            extra=[TagCurveCommand(list(pts), closed=False),
                   RebuildPlaneFacesCommand(*plane)])
    else:
        cmd = build_add_edges(viewport.scene, segments, detect_faces=True,
                              extra=[TagCurveCommand(list(pts), closed=False)])
    viewport.history.execute(cmd)


class ArcTool(PlaneLock, Tool):
    name = "Arc"
    shortcut = "A"
    vcb_label = "Bulge"

    #: Within this many screen pixels of the tangent bulge, the arc snaps
    #: to it (SketchUp's "Tangent at Vertex", cyan).
    TANGENT_PX = 8.0

    def __init__(self) -> None:
        self.start_point: QVector3D | None = None
        self.end_point: QVector3D | None = None
        self.hover_point: QVector3D | None = None
        self.work_plane: tuple[QVector3D, QVector3D] | None = None
        # Tangent direction of the arc this one starts from (at its end
        # vertex), and the bulge that keeps the new arc tangent to it.
        self._tangent_dir: QVector3D | None = None
        self._snap_bulge: float | None = None
        self._viewport = None

    # ---- Lifecycle ----------------------------------------------------------
    def on_activate(self, viewport) -> None:
        self._reset()

    def on_deactivate(self, viewport) -> None:
        self._reset()
        self.hover_point = None

    # ---- Spatial input ------------------------------------------------------
    def on_click(self, ctx: ToolContext) -> None:
        self.note_plane(ctx.viewport)
        self._viewport = ctx.viewport
        if self.start_point is None:
            self.start_point = ctx.world
            if self.work_plane is None:
                self.work_plane = self.locked_work_plane(ctx.world)
            return
        if self.end_point is None:
            if (ctx.world - self.start_point).length() < 1e-6:
                return
            self.end_point = ctx.world
            self._tangent_dir = self._tangent_at_start(ctx.viewport)
            return
        pts = self._points(ctx.world)
        if len(pts) >= 2:
            self._commit(ctx.viewport, pts)

    def on_hover(self, ctx: ToolContext) -> None:
        self.note_plane(ctx.viewport)
        self._viewport = ctx.viewport
        self.hover_point = ctx.world
        self._snap_bulge = None
        self.wireframe_color = self.lock_color()
        if self.end_point is not None and self._tangent_dir is not None:
            h_t = self._tangent_bulge()
            if h_t is not None:
                u, v = self._axes()
                e2 = self._to2(self.end_point, u, v)
                length = math.hypot(*e2)
                perp = u * (-e2[1] / length) + v * (e2[0] / length)
                mid = (self.start_point + self.end_point) * 0.5
                scale = self.world_per_pixel(ctx.viewport, mid, perp)
                tol = (scale or 0.0) * self.TANGENT_PX
                if scale is not None and abs(self._bulge_for(ctx.world) - h_t) <= tol:
                    self._snap_bulge = h_t
                    from core.snap import COLOR_TANGENT
                    self.wireframe_color = (*COLOR_TANGENT, 1.0)
        ctx.viewport.update()

    # ---- Tangent at vertex (SketchUp) ----------------------------------------
    def _tangent_at_start(self, viewport) -> QVector3D | None:
        """The direction an existing arc leaves its END vertex when that
        vertex is our start point — the tangent this arc can continue."""
        scene = getattr(viewport, "scene", None)
        mesh = getattr(scene, "mesh", None)
        if mesh is None or self.start_point is None:
            return None
        # The loose mesh first, then every placed group / component in its
        # own space (SketchUp infers to geometry inside them from outside).
        spaces = [(mesh, None)]
        placements = getattr(viewport, "_placements", None)
        if callable(placements):
            for g in placements():
                gm = getattr(g, "mesh", None)
                if gm is not None and gm.edges and not getattr(g, "billboard", False):
                    spaces.append((gm, getattr(g, "xform", None)))
        for gm, xf in spaces:
            inv = None
            if xf is not None:
                inv, ok = xf.inverted()
                if not ok:
                    continue
            P = inv.map(self.start_point) if inv is not None else self.start_point
            t = self._tangent_in_mesh(gm, P)
            if t is None:
                continue
            if xf is not None:
                t = xf.mapVector(t)
                if t.length() < 1e-9:
                    continue
                t = t.normalized()
            return t
        return None

    @staticmethod
    def _tangent_in_mesh(mesh, P: QVector3D) -> QVector3D | None:
        from core.snap import fit_circle
        for edge in mesh.edges:
            if getattr(edge, "curve", None) is None:
                continue
            if (edge.a - P).length() > 1e-6 and (edge.b - P).length() > 1e-6:
                continue
            chain = mesh.curve_edges(edge)
            incident = [e for e in chain
                        if (e.a - P).length() <= 1e-6 or (e.b - P).length() <= 1e-6]
            if len(incident) != 1:
                continue                       # not the arc's end
            e = incident[0]
            Q = e.b if (e.a - P).length() <= 1e-6 else e.a
            pts: dict = {}
            for c in chain:
                for vv in (c.v0, c.v1):
                    pts[id(vv)] = vv.position
            fit = fit_circle(list(pts.values())) if len(pts) >= 3 else None
            if fit is None:
                continue
            radial = (P - fit[0])
            if radial.length() < 1e-9:
                continue
            r_hat = radial.normalized()
            leaving = P - Q
            t = leaving - r_hat * QVector3D.dotProduct(leaving, r_hat)
            if t.length() < 1e-9:
                continue
            return t.normalized()
        return None

    def _tangent_bulge(self) -> float | None:
        """The signed bulge that makes this arc leave the start along
        ``_tangent_dir``: for a chord of length L meeting the tangent at
        angle a, the sagitta is (L/2)·tan(a/2), on the tangent's side."""
        if self._tangent_dir is None or self.end_point is None:
            return None
        u, v = self._axes()
        e2 = self._to2(self.end_point, u, v)
        length = math.hypot(*e2)
        if length < 1e-9:
            return None
        cx, cy = e2[0] / length, e2[1] / length
        tx = QVector3D.dotProduct(self._tangent_dir, u)
        ty = QVector3D.dotProduct(self._tangent_dir, v)
        tl = math.hypot(tx, ty)
        if tl < 1e-6:
            return None                        # tangent leaves the plane
        tx, ty = tx / tl, ty / tl
        angle = math.atan2(cx * ty - cy * tx, cx * tx + cy * ty)
        if abs(abs(angle) - math.pi) < 1e-3:
            return None                        # doubling back: no arc
        return (length / 2.0) * math.tan(angle / 2.0)

    def on_value(self, viewport, value) -> bool:
        if self.end_point is None or self.hover_point is None:
            return False
        if isinstance(value, tuple):
            return False
        sign = -1.0 if self._bulge_for(self.hover_point) < 0 else 1.0
        pts = self._points(None, bulge=sign * value)
        if len(pts) >= 2:
            self._commit(viewport, pts)
        return True

    def on_radius_value(self, viewport, radius: float) -> bool:
        """SketchUp's "2r": type the RADIUS instead of the bulge. The minor
        arc is taken (like SketchUp); a radius smaller than half the chord
        is impossible and is refused with a status message."""
        if self.end_point is None or radius <= 0:
            return False
        half = (self.end_point - self.start_point).length() * 0.5
        if half < 1e-9:
            return False
        if radius < half - 1e-9:
            viewport.flash_status(tr(
                "Radius {r} m is smaller than half the chord ({h} m)",
                r=f"{radius:.2f}", h=f"{half:.2f}"))
            return True
        radius = max(radius, half)
        h = radius - math.sqrt(max(radius * radius - half * half, 0.0))
        sign = 1.0
        if self.hover_point is not None and self._bulge_for(self.hover_point) < 0:
            sign = -1.0
        pts = self._points(None, bulge=sign * h)
        if len(pts) >= 2:
            self._commit(viewport, pts)
        return True

    def on_cancel(self, viewport) -> None:
        self._reset()
        viewport.update()

    # ---- Preview ------------------------------------------------------------
    def rubber_band_lines(self):
        if self.start_point is None or self.hover_point is None:
            return []
        if self.end_point is None:
            return [(self.start_point, self.hover_point)]   # the chord
        pts = self._points(self.hover_point)
        return [(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]

    def value_label(self):
        if self.end_point is None or self.hover_point is None:
            return None
        mid = (self.start_point + self.end_point) * 0.5
        if self._snap_bulge is not None:
            return (tr("Tangent at vertex") + f"  {abs(self._snap_bulge):.2f} m", mid)
        b = self._bulge_for(self.hover_point)
        return (f"Bulge {abs(b):.2f} m", mid)

    # ---- Internals ----------------------------------------------------------
    def _axes(self) -> tuple[QVector3D, QVector3D]:
        normal = self.drawing_plane()[1]
        return plane_axes(normal)

    def _to2(self, p, u, v):
        d = p - self.start_point
        return (QVector3D.dotProduct(d, u), QVector3D.dotProduct(d, v))

    def _bulge_for(self, cursor: QVector3D) -> float:
        """Signed perpendicular distance from the chord midpoint to the cursor."""
        u, v = self._axes()
        e2 = self._to2(self.end_point, u, v)
        length = math.hypot(*e2)
        if length < 1e-9:
            return 0.0
        px, py = -e2[1] / length, e2[0] / length
        mid = (e2[0] / 2.0, e2[1] / 2.0)
        c2 = self._to2(cursor, u, v)
        return (c2[0] - mid[0]) * px + (c2[1] - mid[1]) * py

    def _points(self, cursor, bulge: float | None = None) -> list[QVector3D]:
        u, v = self._axes()
        s2 = (0.0, 0.0)
        e2 = self._to2(self.end_point, u, v)
        length = math.hypot(*e2)
        if length < 1e-9:
            return []
        if bulge is not None:
            h = bulge
        elif self._snap_bulge is not None:
            h = self._snap_bulge                        # tangent to the arc before
        else:
            h = self._bulge_for(cursor)
        if abs(h) < 1e-4:
            return [self.start_point, self.end_point]   # flat → straight chord
        px, py = -e2[1] / length, e2[0] / length
        mid = (e2[0] / 2.0, e2[1] / 2.0)
        apex = (mid[0] + px * h, mid[1] + py * h)
        pts2 = _arc_3pts_2d(s2, apex, e2, _SEGMENTS)
        return [self.start_point + u * x + v * y for x, y in pts2]

    def _commit(self, viewport, pts: list[QVector3D]) -> None:
        commit_arc(viewport, pts)
        self._reset()
        viewport.update()


    def on_key(self, viewport, key: int, modifiers) -> bool:
        return self.plane_lock_key(viewport, key)

    def _reset(self) -> None:
        self.start_point = None
        self.end_point = None
        self.work_plane = None
        self.hover_plane = None
        self.plane_lock = None
        self._tangent_dir = None
        self._snap_bulge = None
        self.wireframe_color = None


class ThreePointArcTool(PlaneLock, Tool):
    """3-point arc: the arc passes through all three clicked points.

    Click start, click a second point the arc runs through, then move and click
    the end point. The circle through the three points defines the arc.
    """
    name = "3-Point Arc"
    shortcut = "J"

    def __init__(self) -> None:
        self.start_point: QVector3D | None = None
        self.mid_point: QVector3D | None = None
        self.hover_point: QVector3D | None = None
        self.work_plane: tuple[QVector3D, QVector3D] | None = None

    def on_activate(self, viewport) -> None:
        self._reset()

    def on_deactivate(self, viewport) -> None:
        self._reset()
        self.hover_point = None

    def on_click(self, ctx: ToolContext) -> None:
        self.note_plane(ctx.viewport)
        if self.start_point is None:
            self.start_point = ctx.world
            if self.work_plane is None:
                self.work_plane = self.locked_work_plane(ctx.world)
            return
        if self.mid_point is None:
            if (ctx.world - self.start_point).length() < 1e-6:
                return
            self.mid_point = ctx.world
            return
        pts = self._points(ctx.world)
        if len(pts) >= 2:
            self._commit(ctx.viewport, pts)

    def on_hover(self, ctx: ToolContext) -> None:
        self.note_plane(ctx.viewport)
        self.hover_point = ctx.world
        ctx.viewport.update()

    def on_cancel(self, viewport) -> None:
        self._reset()
        viewport.update()

    def rubber_band_lines(self):
        if self.start_point is None or self.hover_point is None:
            return []
        if self.mid_point is None:
            return [(self.start_point, self.hover_point)]
        pts = self._points(self.hover_point)
        return [(pts[i], pts[i + 1]) for i in range(len(pts) - 1)]

    def _axes(self):
        normal = self.drawing_plane()[1]
        return plane_axes(normal)

    def _points(self, end: QVector3D) -> list[QVector3D]:
        u, v = self._axes()

        def to2(p):
            d = p - self.start_point
            return (QVector3D.dotProduct(d, u), QVector3D.dotProduct(d, v))

        s2, m2, e2 = (0.0, 0.0), to2(self.mid_point), to2(end)
        if math.hypot(*e2) < 1e-9 or math.hypot(*m2) < 1e-9:
            return []
        pts2 = _arc_3pts_2d(s2, m2, e2, _SEGMENTS)
        return [self.start_point + u * x + v * y for x, y in pts2]

    def _commit(self, viewport, pts: list[QVector3D]) -> None:
        commit_arc(viewport, pts)
        self._reset()
        viewport.update()


    def on_key(self, viewport, key: int, modifiers) -> bool:
        return self.plane_lock_key(viewport, key)

    def _reset(self) -> None:
        self.start_point = None
        self.mid_point = None
        self.work_plane = None
        self.hover_plane = None
        self.plane_lock = None


class CenterArcTool(PlaneLock, Tool):
    """Compass arc (SketchUp's protractor 'Arc'): centre → start point (the
    radius and 0° arm) → sweep angle. The polyline samples at the same 15°
    pitch as the 24-side circle, so a centre arc drawn concentric with a
    circle lands on the exact same lattice and welds cleanly."""

    name = "Center Arc"
    #: Shift+O, not O: in SketchUp plain O is Orbit and the centre arc has no
    #: default key at all. Sharing O made Qt call the shortcut ambiguous and
    #: fire NEITHER — see tests/test_shortcuts.py.
    shortcut = "Shift+O"
    vcb_label = "Angle"

    _PITCH_DEG = 15.0

    def __init__(self) -> None:
        self.start_point: QVector3D | None = None   # the centre
        self.arm_point: QVector3D | None = None     # radius + 0° direction
        self.hover_point: QVector3D | None = None
        self.work_plane: tuple[QVector3D, QVector3D] | None = None

    # ---- Lifecycle ----------------------------------------------------------
    def on_activate(self, viewport) -> None:
        self._reset()

    def on_deactivate(self, viewport) -> None:
        self._reset()
        self.hover_point = None

    # ---- Spatial input ------------------------------------------------------
    def on_click(self, ctx: ToolContext) -> None:
        self.note_plane(ctx.viewport)
        if self.start_point is None:
            self.start_point = ctx.world
            if self.work_plane is None:
                self.work_plane = self.locked_work_plane(ctx.world)
            return
        if self.arm_point is None:
            if (ctx.world - self.start_point).length() < 1e-6:
                return
            self.arm_point = ctx.world
            return
        pts = self._points(self._sweep_to(ctx.world))
        if len(pts) >= 2:
            self._commit(ctx.viewport, pts)

    def on_hover(self, ctx: ToolContext) -> None:
        self.note_plane(ctx.viewport)
        self.hover_point = ctx.world
        ctx.viewport.update()

    def on_value(self, viewport, value) -> bool:
        if self.arm_point is None or isinstance(value, tuple):
            return False
        sign = -1.0
        if self.hover_point is not None:
            sweep = self._sweep_to(self.hover_point)
            sign = -1.0 if sweep < 0 else 1.0
        pts = self._points(sign * abs(value))
        if len(pts) >= 2:
            self._commit(viewport, pts)
        return True

    def on_cancel(self, viewport) -> None:
        self._reset()
        viewport.update()

    # ---- Preview ------------------------------------------------------------
    def rubber_band_lines(self):
        if self.start_point is None or self.hover_point is None:
            return []
        if self.arm_point is None:
            return [(self.start_point, self.hover_point)]     # the radius arm
        segments = [(self.start_point, self.arm_point),
                    (self.start_point, self.hover_point)]
        pts = self._points(self._sweep_to(self.hover_point))
        segments.extend(zip(pts, pts[1:]))
        return segments

    def value_label(self):
        if self.hover_point is None or self.start_point is None:
            return None
        if self.arm_point is None:
            r = (self.hover_point - self.start_point).length()
            return (f"R {r:.2f} m", self.hover_point)
        return (f"{self._sweep_to(self.hover_point):+.1f}°", self.hover_point)

    def vcb_caption(self) -> str:
        return "Angle" if self.arm_point is not None else "Radius"

    # ---- Internals ----------------------------------------------------------
    def _axes(self):
        normal = self.drawing_plane()[1]
        return plane_axes(normal)

    def _sweep_to(self, cursor: QVector3D) -> float:
        """Signed sweep (degrees) from the 0° arm to the cursor."""
        u, v = self._axes()
        a = self.arm_point - self.start_point
        b = cursor - self.start_point
        a0 = math.atan2(QVector3D.dotProduct(a, v), QVector3D.dotProduct(a, u))
        b0 = math.atan2(QVector3D.dotProduct(b, v), QVector3D.dotProduct(b, u))
        deg = math.degrees(b0 - a0)
        while deg <= -180.0:
            deg += 360.0
        while deg > 180.0:
            deg -= 360.0
        return deg

    def _points(self, sweep_deg: float) -> list[QVector3D]:
        if abs(sweep_deg) < 1e-6:
            return []
        u, v = self._axes()
        a = self.arm_point - self.start_point
        r = math.hypot(QVector3D.dotProduct(a, u), QVector3D.dotProduct(a, v))
        if r < 1e-6:
            return []
        a0 = math.atan2(QVector3D.dotProduct(a, v), QVector3D.dotProduct(a, u))
        steps = max(1, round(abs(sweep_deg) / self._PITCH_DEG))
        out = []
        for k in range(steps + 1):
            t = a0 + math.radians(sweep_deg) * k / steps
            out.append(self.start_point
                       + (u * math.cos(t) + v * math.sin(t)) * r)
        return out

    def _commit(self, viewport, pts: list[QVector3D]) -> None:
        commit_arc(viewport, pts)
        self._reset()
        viewport.update()


    def on_key(self, viewport, key: int, modifiers) -> bool:
        return self.plane_lock_key(viewport, key)

    def _reset(self) -> None:
        self.start_point = None
        self.arm_point = None
        self.work_plane = None
        self.hover_plane = None
        self.plane_lock = None


class PieTool(CenterArcTool):
    """SketchUp's Pie: the centre arc whose wedge CLOSES — the two radius
    edges join the arc's ends to the centre and the slice becomes a face.
    Same clicks as Center Arc: centre, radius arm, sweep."""

    name = "Pie"
    shortcut = None

    def _commit(self, viewport, pts: list[QVector3D]) -> None:
        centre = QVector3D(self.start_point)
        commit_arc(viewport, pts, close_to=centre)
        self._reset()
        viewport.update()
