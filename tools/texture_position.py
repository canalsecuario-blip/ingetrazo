# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""Position Texture: SketchUp's fixed pins on one face (Rafael's review of
2026-09-10, C1: «no encontré manera de cambiar la escala a la textura»).

Right-click a textured face ▸ Texture ▸ Position. The image shows with a
dotted tile grid and four pins on the corners of the tile under the cursor:

* **red** — drag to MOVE the texture (dragging the texture itself does the
  same);
* **green** — drag to SCALE and ROTATE about the red pin; the rotation
  SNAPS at every 45° from the face's own axes (0° = straight with the
  wall, 90° upright, 45° diagonal) with a guide line through the red pin,
  so a texture lands square without eyeballing it — Rafael's review of
  2026-09-16 («en SketchUp te bloquea a los 0, a los 45 y a los 90… si no
  es como un poco a ojo»). Shift while dragging turns the snap off;
* **blue** — drag to SCALE vertically and SHEAR (red and green stay);
* **yellow** — SketchUp's perspective distort. The engine maps textures
  with an affine map per face (what every exporter writes), so this pin is
  shown but not draggable yet.

A single click on a pin LIFTS it: it floats with the cursor, without
changing the texture, and the next click sets it down — the way to put the
red pin on a corner of the face before scaling from there. Right-click
inside the tool: Done, Reset, Flip, Rotate, Undo. Enter or a click outside
the face finishes; Esc first restores the position (and stays), a second
Esc leaves without changes.

The result is the face's world→UV affine map (``attrs["texture"]["uvw"]``,
see :func:`core.texture.face_uv_axes`): the viewport, the .skp/.dae/.obj
writers and the paint sampler all read that one map, so what is placed
here is what SketchUp shows for the same file.
"""
from __future__ import annotations

import math

from PySide6.QtCore import Qt
from PySide6.QtGui import QVector3D

from core.i18n import tr
from core.texture import face_uv_axes
from tools.base import Tool, ToolContext

PIN_MOVE, PIN_SCALE_ROTATE, PIN_SCALE_SHEAR, PIN_DISTORT = range(4)

#: RGB of each pin, SketchUp's order: red, green, blue, yellow.
PIN_COLORS = ((0.86, 0.22, 0.27), (0.16, 0.62, 0.36),
              (0.20, 0.40, 0.78), (0.95, 0.78, 0.20))
PIN_NAMES = ("Move", "Scale / Rotate", "Scale / Shear", "Distort")


def _plane_basis(gu: QVector3D, gv: QVector3D, normal: QVector3D):
    """The tile axes ``(e_u, e_v)`` dual to the map's gradients within the
    face plane: ``gu·e_u = 1, gu·e_v = 0, gv·e_v = 1, gv·e_u = 0``, so one
    tile spans ``e_u`` along U and ``e_v`` along V. ``None`` when the map
    is degenerate."""
    n = QVector3D(normal)
    if n.lengthSquared() < 1e-18:
        return None
    n = n.normalized()
    gu = gu - n * QVector3D.dotProduct(gu, n)
    gv = gv - n * QVector3D.dotProduct(gv, n)
    g11 = QVector3D.dotProduct(gu, gu)
    g12 = QVector3D.dotProduct(gu, gv)
    g22 = QVector3D.dotProduct(gv, gv)
    det = g11 * g22 - g12 * g12
    if abs(det) < 1e-24:
        return None
    return ((gu * g22 - gv * g12) / det, (gv * g11 - gu * g12) / det)


def _gradients(e_u: QVector3D, e_v: QVector3D):
    """Inverse of :func:`_plane_basis`: the map's gradients from the tile
    axes. ``None`` when the axes are (nearly) parallel."""
    g11 = QVector3D.dotProduct(e_u, e_u)
    g12 = QVector3D.dotProduct(e_u, e_v)
    g22 = QVector3D.dotProduct(e_v, e_v)
    det = g11 * g22 - g12 * g12
    if abs(det) < 1e-24:
        return None
    return ((e_u * g22 - e_v * g12) / det, (e_v * g11 - e_u * g12) / det)


def _rotated(vec: QVector3D, axis: QVector3D, angle: float) -> QVector3D:
    """Rodrigues: ``vec`` turned by ``angle`` radians about unit ``axis``."""
    c, s = math.cos(angle), math.sin(angle)
    return (vec * c + QVector3D.crossProduct(axis, vec) * s
            + axis * (QVector3D.dotProduct(axis, vec) * (1.0 - c)))


class TextureMap:
    """The working placement: an anchor ``R`` carrying UV ``(u_r, v_r)`` and
    the tile axes ``e_u``/``e_v`` on the face plane. Everything the pins do
    is an edit of these; the face's ``uvw`` is read back from them."""

    __slots__ = ("R", "uv", "e_u", "e_v")

    def __init__(self, R, uv, e_u, e_v) -> None:
        self.R = QVector3D(R)
        self.uv = (float(uv[0]), float(uv[1]))
        self.e_u = QVector3D(e_u)
        self.e_v = QVector3D(e_v)

    def copy(self) -> "TextureMap":
        return TextureMap(self.R, self.uv, self.e_u, self.e_v)

    def world(self, u: float, v: float) -> QVector3D:
        return (self.R + self.e_u * (u - self.uv[0])
                + self.e_v * (v - self.uv[1]))

    def uv_of(self, p: QVector3D):
        g = _gradients(self.e_u, self.e_v)
        if g is None:
            return self.uv
        d = p - self.R
        return (self.uv[0] + QVector3D.dotProduct(g[0], d),
                self.uv[1] + QVector3D.dotProduct(g[1], d))

    def uvw(self) -> list | None:
        """``[gu.xyz, cu, gv.xyz, cv]`` — the face's world→UV affine map."""
        g = _gradients(self.e_u, self.e_v)
        if g is None:
            return None
        gu, gv = g
        cu = self.uv[0] - QVector3D.dotProduct(gu, self.R)
        cv = self.uv[1] - QVector3D.dotProduct(gv, self.R)
        return [gu.x(), gu.y(), gu.z(), cu, gv.x(), gv.y(), gv.z(), cv]

    @staticmethod
    def from_face(face, tex: dict, at: QVector3D | None = None):
        """The face's current map, anchored at the tile corner below
        ``at`` (the click point) — where SketchUp puts the red pin."""
        normal = face.normal()
        gu, cu, gv, cv = face_uv_axes(tex, normal)
        basis = _plane_basis(gu, gv, normal)
        if basis is None:
            return None
        e_u, e_v = basis
        pts = list(face.vertices)
        if at is None:
            at = QVector3D()
            for p in pts:
                at += p
            at /= float(max(len(pts), 1))
        u = QVector3D.dotProduct(gu, at) + cu
        v = QVector3D.dotProduct(gv, at) + cv
        u0, v0 = math.floor(u), math.floor(v)
        R = at + e_u * (u0 - u) + e_v * (v0 - v)
        return TextureMap(R, (u0, v0), e_u, e_v)


class TexturePositionTool(Tool):
    name = "Position Texture"
    icon = "texture_position"
    uses_snap = False
    #: The viewport shows this Qt cursor while the tool is active (SketchUp's
    #: hand) — the tool has no drawn icon cursor.
    qt_cursor = Qt.OpenHandCursor
    #: Opacity of the live preview (SketchUp shows the texture translucent
    #: with the dotted tile grid over it).
    preview_opacity = 0.75
    #: Pixel radius that grabs a pin.
    GRAB_PX = 12.0
    #: Press/release closer than this is a click (lifts a pin), not a drag.
    CLICK_PX = 4.0
    #: Pin half-size, px.
    PIN_PX = 7.0
    #: The green pin's rotation snaps within this many degrees of every
    #: multiple of SNAP_STEP_DEG, measured from the face's own axes.
    SNAP_TOL_DEG = 4.0
    SNAP_STEP_DEG = 45.0

    def __init__(self) -> None:
        self.face = None
        self.side = "front"
        self._tex0: dict | None = None
        self._entry: TextureMap | None = None
        self.map: TextureMap | None = None
        self.pin_uv: list[tuple[float, float]] = []
        self._lifted: int | None = None
        self._lifted_pos: QVector3D | None = None
        self._drag = None            # ("pin", i, state0) | ("texture", state0)
        self._drag_start: QVector3D | None = None
        self._press_px = None
        self._moved = False
        self._undo: list[tuple[TextureMap, list]] = []
        self._hover_pin: int | None = None
        #: While the green pin drags: the angle (deg, from the face's own
        #: axes) the rotation is snapped to, or None when free.
        self._snap_deg: float | None = None
        self._snap_free = False          # Shift held: no snapping
        self._cursor: QVector3D | None = None
        self._viewport = None
        self._esc_armed = False
        self._plane = None

    # ---- Entry ----------------------------------------------------------------
    @staticmethod
    def side_texture(face, side: str):
        """The image texture dict of ``face``'s ``side`` ("front"/"back"),
        or ``None``. A back painted as a mirror of the front (``True``)
        has no texture of its own."""
        attrs = getattr(face, "attrs", None) or {}
        if side == "back":
            back = attrs.get("back")
            tex = back.get("texture") if isinstance(back, dict) else None
        else:
            tex = attrs.get("texture")
        if not tex or not tex.get("path"):
            return None
        return tex

    def begin(self, viewport, face, at: QVector3D | None = None,
              side: str = "front") -> bool:
        """Start positioning the texture of ``face``'s ``side`` with the
        pins on the tile under ``at``. Returns False when that side has no
        image texture. The back side projects with the same plane basis as
        the front (the renderer builds both from the face normal), so one
        map serves either; only where it is stored differs."""
        tex = self.side_texture(face, side)
        if tex is None:
            return False
        self.side = side
        m = TextureMap.from_face(face, tex, at)
        if m is None:
            return False
        self.face = face
        self._viewport = viewport
        self._tex0 = dict(tex)
        self._entry = m.copy()
        self.map = m
        u0, v0 = m.uv
        self.pin_uv = [(u0, v0), (u0 + 1.0, v0), (u0, v0 + 1.0),
                       (u0 + 1.0, v0 + 1.0)]
        self._undo = []
        self._lifted = None
        self._drag = None
        self._esc_armed = False
        n = face.normal()
        self._plane = (QVector3D(face.vertices[0]), n.normalized()
                       if n.lengthSquared() > 1e-18 else QVector3D(0, 0, 1))
        # The face's own axes — what "straight with the wall" means: the
        # default projection's U (horizontal along a wall) and V (up).
        from core.texture import projection_axes
        self._ref_axes = projection_axes(self._plane[1])
        self._snap_deg = None
        suppress = getattr(viewport, "set_suppressed_faces", None)
        if suppress is not None:
            suppress({face})
        flash = getattr(viewport, "flash_status", None)
        if flash is not None:
            flash(tr("Drag the texture or a pin — red moves, green scales and "
                     "rotates, blue scales and shears. Enter finishes."), 6000)
        update = getattr(viewport, "update", None)
        if update is not None:
            update()
        return True

    @property
    def active(self) -> bool:
        return self.face is not None and self.map is not None

    @property
    def dragging(self) -> bool:      # keeps Esc inside the tool (viewport rule)
        return self.active

    # ---- Lifecycle ------------------------------------------------------------
    def on_activate(self, viewport) -> None:
        self._viewport = viewport

    def on_deactivate(self, viewport) -> None:
        self._leave(viewport)

    def _leave(self, viewport) -> None:
        suppress = getattr(viewport, "set_suppressed_faces", None)
        if suppress is not None:
            suppress(set())
        self.face = None
        self.map = None
        self._entry = None
        self._tex0 = None
        self._drag = None
        self._lifted = None
        self._undo = []
        self._hover_pin = None
        self._esc_armed = False

    def _exit(self, viewport) -> None:
        """Back to Select (SketchUp returns to the previous tool)."""
        self._leave(viewport)
        win = viewport.window() if hasattr(viewport, "window") else None
        activate = getattr(win, "_activate_tool", None)
        if activate is not None:
            activate("select")
        else:
            set_tool = getattr(viewport, "set_active_tool", None)
            if set_tool is not None:
                set_tool(None)
        update = getattr(viewport, "update", None)
        if update is not None:
            update()

    # ---- Geometry helpers -----------------------------------------------------
    def pins(self) -> list[QVector3D]:
        """World position of the four pins (a lifted one floats)."""
        if self.map is None:
            return []
        out = [self.map.world(u, v) for u, v in self.pin_uv]
        if self._lifted is not None and self._lifted_pos is not None:
            out[self._lifted] = QVector3D(self._lifted_pos)
        return out

    def _on_plane(self, viewport, screen) -> QVector3D | None:
        """The cursor's point on the face plane."""
        if self._plane is None or screen is None:
            return None
        ray = getattr(viewport, "_pixel_to_ray", None)
        hit = getattr(viewport, "_ray_plane", None)
        if ray is None or hit is None:
            return None
        origin, direction = ray(screen.x(), screen.y())
        if origin is None:
            return None
        return hit(origin, direction, self._plane[0], self._plane[1])

    def _pin_at(self, viewport, screen) -> int | None:
        to_px = getattr(viewport, "_world_to_pixel", None)
        if to_px is None or screen is None:
            return None
        best = None
        for i, p in enumerate(self.pins()):
            q = to_px(p)
            if q is None:
                continue
            d = math.hypot(q[0] - screen.x(), q[1] - screen.y())
            if d <= self.GRAB_PX and (best is None or d < best[0]):
                best = (d, i)
        return None if best is None else best[1]

    def _on_face(self, viewport, screen) -> bool:
        pick = getattr(viewport, "pick_face", None)
        if pick is None or screen is None:
            return True
        return pick(screen.x(), screen.y()) is self.face

    # ---- Mouse ----------------------------------------------------------------
    def on_click(self, ctx: ToolContext) -> None:
        if not self.active:
            return
        vp = ctx.viewport
        self._viewport = vp
        self._press_px = ctx.screen
        self._moved = False
        self._esc_armed = False
        if self._lifted is not None:
            # Set the floating pin down: it now holds the UV under it.
            p = self._on_plane(vp, ctx.screen)
            if p is not None:
                self.pin_uv[self._lifted] = self.map.uv_of(p)
            self._lifted = None
            self._lifted_pos = None
            self._drag = None
            vp.update()
            return
        pin = self._pin_at(vp, ctx.screen)
        if pin is not None:
            if pin == PIN_DISTORT:
                vp.flash_status(tr("Distort (perspective) is not available yet — "
                                   "use the red, green and blue pins."), 4000)
                self._drag = None
                return
            self._drag = ("pin", pin, self.map.copy(), list(self.pin_uv))
            self._drag_start = self._on_plane(vp, ctx.screen)
            return
        if self._on_face(vp, ctx.screen):
            self._drag = ("texture", self.map.copy(), list(self.pin_uv))
            self._drag_start = self._on_plane(vp, ctx.screen)
            return
        # A click outside the face: Done (SketchUp).
        self.commit(vp)

    def on_hover(self, ctx: ToolContext) -> None:
        if not self.active:
            return
        vp = ctx.viewport
        self._viewport = vp
        p = self._on_plane(vp, ctx.screen)
        self._cursor = p
        if self._press_px is not None and not self._moved and ctx.screen is not None:
            if (math.hypot(ctx.screen.x() - self._press_px.x(),
                           ctx.screen.y() - self._press_px.y()) > self.CLICK_PX):
                self._moved = True
        if self._lifted is not None:
            if p is not None:
                self._lifted_pos = p
            vp.update()
            return
        if self._drag is not None and self._moved and p is not None \
                and self._drag_start is not None:
            self._snap_free = bool(ctx.modifiers & Qt.ShiftModifier)
            self._apply_drag(p)
            vp.update()
            return
        self._hover_pin = self._pin_at(vp, ctx.screen)
        vp.update()

    def on_release(self, viewport) -> None:
        if not self.active or self._drag is None:
            self._press_px = None
            return
        drag = self._drag
        self._drag = None
        self._press_px = None
        self._snap_deg = None
        if not self._moved:
            if drag[0] == "pin":
                # A click on a pin lifts it (SketchUp): it floats with the
                # cursor and the next click sets it down.
                self._lifted = drag[1]
                self._lifted_pos = self.pins()[drag[1]]
                viewport.flash_status(
                    tr("Pin lifted — click where it should sit."), 3000)
            return
        # A finished drag is one undoable step inside the tool.
        before = drag[2] if drag[0] == "pin" else drag[1]
        before_uv = drag[3] if drag[0] == "pin" else drag[2]
        self._undo.append((before, before_uv))
        viewport.update()

    def _apply_drag(self, p: QVector3D) -> None:
        kind = self._drag[0]
        if kind == "texture":
            m0 = self._drag[1]
            delta = p - self._drag_start
            self.map = m0.copy()
            self.map.R = m0.R + delta
            return
        _k, pin, m0, _uv0 = self._drag
        if pin == PIN_MOVE:
            delta = p - self._drag_start
            self.map = m0.copy()
            self.map.R = m0.R + delta
        elif pin == PIN_SCALE_ROTATE:
            self.map = self._scale_rotate(m0, p)
        elif pin == PIN_SCALE_SHEAR:
            self.map = self._scale_shear(m0, p)

    def _scale_rotate(self, m0: TextureMap, p: QVector3D) -> TextureMap:
        """The similarity about the red pin that takes the green pin to
        ``p``: rotation in the face plane plus uniform scale."""
        R = m0.world(*self.pin_uv[PIN_MOVE])
        G = m0.world(*self.pin_uv[PIN_SCALE_ROTATE])
        a, b = G - R, p - R
        la, lb = a.length(), b.length()
        if la < 1e-9 or lb < 1e-9:
            return m0.copy()
        n = self._plane[1]
        s = lb / la
        cos_t = max(-1.0, min(1.0, QVector3D.dotProduct(a, b) / (la * lb)))
        sin_t = QVector3D.dotProduct(n, QVector3D.crossProduct(a, b)) / (la * lb)
        theta = math.atan2(sin_t, cos_t)
        theta = self._snap_rotation(m0, n, theta)
        e_u = _rotated(m0.e_u, n, theta) * s
        e_v = _rotated(m0.e_v, n, theta) * s
        m = TextureMap(R, self.pin_uv[PIN_MOVE], e_u, e_v)
        return m

    def _tile_angle(self, e_u: QVector3D) -> float:
        """Where the tile's U axis points, in degrees from the face's own
        U axis, turning toward its V axis (0 = straight, 90 = upright)."""
        u_ax, v_ax = self._ref_axes
        return math.degrees(math.atan2(QVector3D.dotProduct(e_u, v_ax),
                                       QVector3D.dotProduct(e_u, u_ax)))

    def _snap_rotation(self, m0: TextureMap, n: QVector3D,
                       theta: float) -> float:
        """SketchUp's sticky angles on the green pin: within SNAP_TOL_DEG of
        a multiple of 45° from the face's axes, the rotation lands exactly
        there and ``_snap_deg`` says so (the overlay draws the guide).
        Shift keeps the rotation free."""
        self._snap_deg = None
        if self._snap_free:
            return theta
        angle = self._tile_angle(_rotated(m0.e_u, n, theta))
        step = self.SNAP_STEP_DEG
        target = round(angle / step) * step
        diff = target - angle
        if abs(diff) > self.SNAP_TOL_DEG:
            return theta
        self._snap_deg = target % 360.0
        return theta + math.radians(diff)

    def _scale_shear(self, m0: TextureMap, p: QVector3D) -> TextureMap:
        """The affine map that keeps the red and green pins and takes the
        blue pin to ``p``: vertical scale plus shear."""
        uv_r = self.pin_uv[PIN_MOVE]
        uv_g = self.pin_uv[PIN_SCALE_ROTATE]
        uv_b = self.pin_uv[PIN_SCALE_SHEAR]
        R = m0.world(*uv_r)
        G = m0.world(*uv_g)
        du_g, dv_g = uv_g[0] - uv_r[0], uv_g[1] - uv_r[1]
        du_b, dv_b = uv_b[0] - uv_r[0], uv_b[1] - uv_r[1]
        det = du_g * dv_b - dv_g * du_b
        if abs(det) < 1e-12:
            return m0.copy()
        # [du_g dv_g; du_b dv_b] · [e_u; e_v] = [G−R; p−R]
        g, b = G - R, p - R
        e_u = (g * dv_b - b * dv_g) / det
        e_v = (b * du_g - g * du_b) / det
        if _gradients(e_u, e_v) is None:
            return m0.copy()
        return TextureMap(R, uv_r, e_u, e_v)

    # ---- Menu commands (SketchUp's right-click inside the tool) ---------------
    def _push_undo(self) -> None:
        self._undo.append((self.map.copy(), list(self.pin_uv)))

    def rotate(self, degrees: float) -> None:
        """Turn the texture about the red pin (90 / 180 / 270)."""
        if not self.active:
            return
        self._push_undo()
        R = self.map.world(*self.pin_uv[PIN_MOVE])
        n = self._plane[1]
        a = math.radians(degrees)
        self.map = TextureMap(R, self.pin_uv[PIN_MOVE],
                              _rotated(self.map.e_u, n, a),
                              _rotated(self.map.e_v, n, a))

    def flip(self, horizontal: bool) -> None:
        """Mirror the texture about the red pin: left/right or up/down."""
        if not self.active:
            return
        self._push_undo()
        R = self.map.world(*self.pin_uv[PIN_MOVE])
        e_u, e_v = self.map.e_u, self.map.e_v
        if horizontal:
            e_u = -e_u
        else:
            e_v = -e_v
        self.map = TextureMap(R, self.pin_uv[PIN_MOVE], e_u, e_v)

    def undo_step(self) -> bool:
        if not self._undo:
            return False
        m, uv = self._undo.pop()
        self.map = m.copy()
        self.pin_uv = list(uv)
        self._lifted = None
        return True

    def reset(self) -> None:
        """Back to the placement the tool was entered with."""
        if self._entry is None:
            return
        self._push_undo()
        self.map = self._entry.copy()
        u0, v0 = self.map.uv
        self.pin_uv = [(u0, v0), (u0 + 1.0, v0), (u0, v0 + 1.0),
                       (u0 + 1.0, v0 + 1.0)]
        self._lifted = None

    def changed(self) -> bool:
        if self.map is None or self._entry is None:
            return False
        a, b = self.map.uvw(), self._entry.uvw()
        if a is None or b is None:
            return a is not b
        return any(abs(x - y) > 1e-9 for x, y in zip(a, b))

    def result_texture(self) -> dict | None:
        """The texture dict the face gets on Done."""
        if self.map is None or self._tex0 is None:
            return None
        uvw = self.map.uvw()
        if uvw is None:
            return None
        tex = {k: v for k, v in self._tex0.items() if k != "rot"}
        tex["uvw"] = uvw
        return tex

    def commit(self, viewport) -> None:
        """Done: write the map to the face as one undoable step."""
        if not self.active:
            return
        if self.changed():
            tex = self.result_texture()
            if tex is not None:
                viewport.history.execute(self.side_command(self.face, self.side, tex))
        self._exit(viewport)

    @staticmethod
    def side_command(face, side: str, tex: dict | None):
        """The undoable command that puts ``tex`` on ``face``'s ``side``
        (``None`` clears the texture of that side)."""
        if side == "back":
            from core.history import SetFaceBackCommand
            back = dict(face.attrs.get("back") or {})
            if tex is None:
                back.pop("texture", None)
            else:
                back["texture"] = dict(tex)
            return SetFaceBackCommand([face], [back])
        from core.history import SetFaceTextureCommand
        return SetFaceTextureCommand([face], tex)

    def cancel(self, viewport) -> None:
        self._exit(viewport)

    def on_cancel(self, viewport) -> None:
        """Esc: the first press restores the entry placement and stays; a
        second one (or one with nothing to restore) leaves."""
        if not self.active:
            return
        if self._lifted is not None:
            self._lifted = None
            self._lifted_pos = None
            viewport.update()
            return
        if self.changed() and not self._esc_armed:
            self.reset()
            self._esc_armed = True
            viewport.flash_status(tr("Position restored — Esc again to leave."), 3000)
            viewport.update()
            return
        self.cancel(viewport)

    def on_key(self, viewport, key: int, modifiers) -> bool:
        if not self.active:
            return False
        if key in (Qt.Key_Return, Qt.Key_Enter):
            self.commit(viewport)
            return True
        return False

    def context_menu(self, viewport, global_pos) -> bool:
        """The tool's own right-click menu (replaces the viewport's)."""
        if not self.active:
            return False
        from PySide6.QtWidgets import QMenu
        menu = QMenu(viewport)
        menu.addAction(tr("Done"), lambda: self.commit(viewport))
        menu.addAction(tr("Reset"), lambda: (self.reset(), viewport.update()))
        flip = menu.addMenu(tr("Flip"))
        flip.addAction(tr("Left / Right"), lambda: (self.flip(True), viewport.update()))
        flip.addAction(tr("Up / Down"), lambda: (self.flip(False), viewport.update()))
        rot = menu.addMenu(tr("Rotate"))
        for deg in (90, 180, 270):
            rot.addAction(f"{deg}°", lambda d=deg: (self.rotate(d), viewport.update()))
        undo = menu.addAction(tr("Undo"), lambda: (self.undo_step(), viewport.update()))
        undo.setEnabled(bool(self._undo))
        menu.exec(global_pos)
        return True

    # ---- Preview --------------------------------------------------------------
    def preview_faces(self):
        if not self.active:
            return []
        tex = self.result_texture()
        if tex is None:
            return []
        from core.geometry import Face as PreviewFace
        return [PreviewFace(list(self.face.vertices),
                            [list(h) for h in self.face.holes], {"texture": tex})]

    def grid_lines(self) -> list[tuple[QVector3D, QVector3D]]:
        """The tile lattice over the face's UV extent: SketchUp's «matrix
        of dotted lines»."""
        if not self.active:
            return []
        uvs = [self.map.uv_of(p) for p in self.face.vertices]
        if not uvs:
            return []
        eps = 1e-4                      # float noise must not add a line
        umin = math.floor(min(u for u, _v in uvs) + eps)
        umax = math.ceil(max(u for u, _v in uvs) - eps)
        vmin = math.floor(min(v for _u, v in uvs) + eps)
        vmax = math.ceil(max(v for _u, v in uvs) - eps)
        if (umax - umin) * (vmax - vmin) > 2500:
            return []                       # a tiny tile on a huge face: skip
        lines = []
        for k in range(umin, umax + 1):
            lines.append((self.map.world(k, vmin), self.map.world(k, vmax)))
        for k in range(vmin, vmax + 1):
            lines.append((self.map.world(umin, k), self.map.world(umax, k)))
        return lines

    def draw_overlay(self, viewport, painter) -> None:
        if not self.active:
            return
        from PySide6.QtCore import QPointF
        from PySide6.QtGui import QColor, QPen
        to_px = getattr(viewport, "_world_to_pixel", None)
        if to_px is None:
            return
        pen = QPen(QColor(255, 255, 255, 170), 1.0, Qt.DotLine)
        painter.setPen(pen)
        for a, b in self.grid_lines():
            pa, pb = to_px(a), to_px(b)
            if pa is None or pb is None:
                continue
            painter.drawLine(QPointF(*pa), QPointF(*pb))
        if self._drag is not None and self._drag[0] == "pin" \
                and self._drag[1] == PIN_SCALE_ROTATE and self._moved:
            # SketchUp's dashed guide from the pivot to the green pin.
            R = self.map.world(*self.pin_uv[PIN_MOVE])
            G = self.map.world(*self.pin_uv[PIN_SCALE_ROTATE])
            pr, pg = to_px(R), to_px(G)
            if pr is not None and pg is not None:
                painter.setPen(QPen(QColor(40, 40, 40, 200), 1.0, Qt.DashLine))
                painter.drawLine(QPointF(*pr), QPointF(*pg))
            if self._snap_deg is not None and pr is not None and pg is not None:
                # Snapped: the guide runs on through the red pin both ways,
                # in the inference magenta, and says the angle.
                d = G - R
                reach = max(d.length() * 4.0, 0.5)
                d = d.normalized() * reach
                pa, pb = to_px(R - d), to_px(R + d)
                if pa is not None and pb is not None:
                    painter.setPen(QPen(QColor(210, 40, 190, 220), 1.5,
                                        Qt.DashLine))
                    painter.drawLine(QPointF(*pa), QPointF(*pb))
                painter.setPen(QPen(QColor(30, 30, 30, 255), 1.0))
                painter.drawText(QPointF(pg[0] + 12, pg[1] - 10),
                                 f"{self._snap_deg:g}°")
        half = self.PIN_PX
        for i, p in enumerate(self.pins()):
            q = to_px(p)
            if q is None:
                continue
            r, g, b = PIN_COLORS[i]
            alpha = 120 if i == PIN_DISTORT else 255
            fill = QColor.fromRgbF(r, g, b, alpha / 255.0)
            outline = QColor(255, 255, 255, 240)
            if i == self._hover_pin or i == self._lifted:
                outline = QColor(30, 30, 30, 255)
            painter.setPen(QPen(outline, 2.0))
            painter.setBrush(fill)
            painter.drawRect(q[0] - half, q[1] - half, 2 * half, 2 * half)
            if i == self._lifted:
                painter.setBrush(Qt.NoBrush)
                painter.setPen(QPen(fill, 1.5))
                painter.drawEllipse(QPointF(*q), half * 2.0, half * 2.0)
