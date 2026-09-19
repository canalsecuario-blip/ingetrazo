# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""Walking through a model — SketchUp's Position Camera, Look Around and
Walk (help.sketchup.com, «Walking through a Model»), the way Rafael asked
for it («pasitos» to look at interiors, 2026-09-16, 13:00).

Three tools, as there:

* **Position Camera** — click a point and the eye goes ``EYE_HEIGHT``
  above it (SketchUp's 5' 6" = 1,68 m), looking level the way the camera
  was already heading; the Measurements box («Height offset») takes
  another height. Click-DRAG from where you want to stand to what you
  want to look at. Either way the tool hands over to Look Around.
* **Look Around** — drag to turn your head; the eye stays put. The box
  («Eye height») sets the eye's height.
* **Walk** — click and drag: a crosshair marks the click, and the farther
  the cursor gets from it the faster you go; up/down walks forward and
  back, left/right turns. The eye keeps its height above whatever it is
  standing on (stairs, ramps), and walls stop you. Ctrl = run, Shift =
  move vertically or sideways, Alt = walk through walls — SketchUp's own
  modifiers, read off Marco's recording of its status bar (2026-09-18).

None of it touches the camera model: a walkthrough only ever says "the
eye is here, looking there" (``OrbitCamera.look_from``), and the floor
and the walls are the same visible-face index every pick uses
(``Viewport.ray_distance``).
"""
from __future__ import annotations

import math

from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QVector3D

from core.i18n import tr
from tools.base import Tool, ToolContext

#: SketchUp's default eye height, 5' 6".
DEFAULT_EYE_HEIGHT = 1.68
_SETTINGS_KEY = "walk/eye_height"

_UP = QVector3D(0.0, 0.0, 1.0)


def eye_height() -> float:
    """The eye height the three tools share, remembered across sessions."""
    try:
        from PySide6.QtCore import QSettings
        v = float(QSettings().value(_SETTINGS_KEY, DEFAULT_EYE_HEIGHT))
        return v if 0.05 <= v <= 100.0 else DEFAULT_EYE_HEIGHT
    except Exception:  # noqa: BLE001 — no settings store (tests, scripts)
        return DEFAULT_EYE_HEIGHT


def set_eye_height(value: float) -> None:
    try:
        from PySide6.QtCore import QSettings
        QSettings().setValue(_SETTINGS_KEY, float(value))
    except Exception:  # noqa: BLE001
        pass


def _level_heading(camera) -> QVector3D:
    """The camera's heading flattened to the horizon — where a placed eye
    looks first. Straight up or down has no heading: look north."""
    f = camera.forward()
    h = QVector3D(f.x(), f.y(), 0.0)
    return h.normalized() if h.length() > 1e-6 else QVector3D(0.0, 1.0, 0.0)


def _floor_below(viewport, x: float, y: float, z_from: float):
    """Z of the nearest visible face straight below ``(x, y, z_from)``, or
    ``None`` when the ray meets nothing (open ground: the caller falls back
    to z = 0)."""
    dist = getattr(viewport, "ray_distance", None)
    if dist is None:
        return None
    t = dist(QVector3D(x, y, z_from), QVector3D(0.0, 0.0, -1.0))
    return None if t is None else z_from - t


def _handoff(viewport, key: str) -> None:
    """Switch to another registered tool through the window, so the
    toolbar, the status hint and the Measurements box follow."""
    window = viewport.window() if callable(getattr(viewport, "window", None)) \
        else None
    activate = getattr(window, "_activate_tool", None)
    if callable(activate):
        activate(key)


class _EyeTool(Tool):
    """What the three share: no snap markers on the model, the eye height
    in the Measurements box, and «Eye height» typed there moves the eye."""
    uses_snap = False
    vcb_label = "Eye height"

    def on_activate(self, viewport) -> None:
        self._viewport = viewport

    def on_deactivate(self, viewport) -> None:
        self._viewport = None

    def value_label(self):
        vp = getattr(self, "_viewport", None)
        if vp is None:
            return None
        return (f"{vp.camera.eye().z():.2f} m", None)

    def drag_plane(self, viewport):
        """Look Around and Walk read the cursor in PIXELS; the viewport
        still wants a world point per event, and the ground stops giving
        one above the horizon — where a look-up or a walk toward the sky
        would otherwise freeze (the Push/Pull lesson). A plane facing the
        camera through its target is hit by every ray."""
        cam = viewport.camera
        return QVector3D(cam.target), -cam.forward()

    def on_value(self, viewport, value) -> bool:
        """«Eye height»: the eye's height above the ground — the model's
        z = 0 — as SketchUp's box reads it while you look around or walk."""
        if not isinstance(value, (int, float)):
            return False
        cam = viewport.camera
        eye = cam.eye()
        cam.look_from(QVector3D(eye.x(), eye.y(), float(value)), cam.forward())
        viewport.update()
        return True


class PositionCameraTool(_EyeTool):
    name = "Position Camera"
    uses_snap = True                  # the point you stand on is a snap
    vcb_label = "Height offset"
    DRAG_PX = 6.0

    def __init__(self) -> None:
        self._viewport = None
        self._press = None            # world point pressed (where to stand)
        self._press_px = None
        self._look_at = None          # world point under the cursor while dragging
        self._dragged = False
        self._base = None             # where the eye was last placed (for retyping)

    def on_activate(self, viewport) -> None:
        super().on_activate(viewport)
        self._press = None
        self._look_at = None
        self._dragged = False

    def value_label(self):
        return (f"{eye_height():.2f} m", None)

    def drag_plane(self, viewport):
        return None                   # the click needs a real point to stand on

    def on_click(self, ctx: ToolContext) -> None:
        self._press = QVector3D(ctx.world)
        self._press_px = QPointF(ctx.screen)
        self._look_at = None
        self._dragged = False

    def on_hover(self, ctx: ToolContext) -> None:
        if self._press is None or self._press_px is None:
            return
        if not self._dragged and math.hypot(
                ctx.screen.x() - self._press_px.x(),
                ctx.screen.y() - self._press_px.y()) > self.DRAG_PX:
            self._dragged = True
        if self._dragged:
            self._look_at = QVector3D(ctx.world)
            ctx.viewport.update()

    def on_release(self, viewport) -> None:
        if self._press is None:
            return
        base, look_at, dragged = self._press, self._look_at, self._dragged
        self._press = None
        self._look_at = None
        self._dragged = False
        self.place(viewport, base, look_at if dragged else None)
        _handoff(viewport, "look_around")

    def place(self, viewport, base: QVector3D, look_at=None) -> None:
        """The eye ``eye_height()`` above ``base``, looking at ``look_at`` —
        or level along the camera's heading when there is none. Always in
        perspective: a walkthrough in parallel projection is a plan."""
        cam = viewport.camera
        eye = base + _UP * eye_height()
        if look_at is not None and (look_at - eye).length() > 1e-6:
            direction = look_at - eye
        else:
            direction = _level_heading(cam)
        cam.perspective = True
        cam.look_from(eye, direction)
        self._base = QVector3D(base)
        viewport.update()
        flash = getattr(viewport, "flash_status", None)
        if flash is not None:
            flash(tr("Eye placed {h:.2f} m above the point — drag to look "
                     "around, Walk to move", h=eye_height()), 4000)

    def on_value(self, viewport, value) -> bool:
        """«Height offset»: the eye height itself. Typed after placing, the
        eye moves to the new height over the same spot."""
        if not isinstance(value, (int, float)) or value <= 0.0:
            return False
        set_eye_height(float(value))
        if self._base is not None:
            cam = viewport.camera
            cam.look_from(self._base + _UP * float(value), cam.forward())
            viewport.update()
        return True

    def rubber_band_lines(self):
        if self._press is not None and self._look_at is not None:
            return [(self._press + _UP * eye_height(), self._look_at)]
        return []

    def on_cancel(self, viewport) -> None:
        self._press = None
        self._look_at = None
        self._dragged = False


class LookAroundTool(_EyeTool):
    name = "Look Around"
    #: Degrees of head turn per pixel of drag, scaled to the viewport: a
    #: drag across the whole width is half a turn, the whole height a
    #: quarter (looking straight up to straight down).
    TURN_DEG_PER_WIDTH = 180.0
    PITCH_DEG_PER_HEIGHT = 90.0

    def __init__(self) -> None:
        self._viewport = None
        self._last_px = None

    def on_click(self, ctx: ToolContext) -> None:
        self._last_px = QPointF(ctx.screen)

    def on_hover(self, ctx: ToolContext) -> None:
        if self._last_px is None:
            return
        vp = ctx.viewport
        dx = ctx.screen.x() - self._last_px.x()
        dy = ctx.screen.y() - self._last_px.y()
        self._last_px = QPointF(ctx.screen)
        w = max(1, getattr(vp, "width", lambda: 1000)())
        h = max(1, getattr(vp, "height", lambda: 700)())
        # Drag right = look right; drag up = look up (screen y runs down).
        vp.camera.turn(dx * self.TURN_DEG_PER_WIDTH / w,
                       -dy * self.PITCH_DEG_PER_HEIGHT / h)
        vp.update()

    def on_release(self, viewport) -> None:
        self._last_px = None

    def on_cancel(self, viewport) -> None:
        self._last_px = None


class WalkTool(_EyeTool):
    name = "Walk"
    #: Pixels of drag from the crosshair for full walking speed, the speed
    #: itself (m/s), and how much faster Ctrl runs.
    FULL_PX = 150.0
    WALK_SPEED = 1.5
    RUN_FACTOR = 3.0
    TURN_DEG_PER_S = 60.0
    DEAD_PX = 4.0
    TICK_MS = 33
    #: How close the eye may come to a wall, and a second feeler just
    #: above the knee so a parapet or a table stops you too.
    CLEARANCE = 0.35
    #: The biggest rise the feet take in one step (a stair riser, a kerb);
    #: anything taller is a wall — so the low feeler runs just above it.
    STEP_UP = 0.5
    KNEE = 0.55

    def __init__(self) -> None:
        self._viewport = None
        self._anchor_px = None
        self._cursor_px = None
        self._timer = None
        self._modifiers = Qt.NoModifier

    def on_activate(self, viewport) -> None:
        super().on_activate(viewport)
        self._anchor_px = None
        self._cursor_px = None

    def on_deactivate(self, viewport) -> None:
        self._stop()
        super().on_deactivate(viewport)

    # ---- Stroke ---------------------------------------------------------------
    def on_click(self, ctx: ToolContext) -> None:
        self._anchor_px = QPointF(ctx.screen)
        self._cursor_px = QPointF(ctx.screen)
        self._modifiers = ctx.modifiers
        self._start(ctx.viewport)

    def on_hover(self, ctx: ToolContext) -> None:
        if self._anchor_px is None:
            return
        self._cursor_px = QPointF(ctx.screen)
        self._modifiers = ctx.modifiers

    def on_release(self, viewport) -> None:
        self._stop()
        self._anchor_px = None
        self._cursor_px = None
        viewport.update()

    def on_cancel(self, viewport) -> None:
        self.on_release(viewport)

    def _start(self, viewport) -> None:
        if self._timer is None:
            from PySide6.QtCore import QTimer
            self._timer = QTimer(viewport)
            self._timer.setInterval(self.TICK_MS)
            self._timer.timeout.connect(self._tick)
        self._timer.start()

    def _stop(self) -> None:
        if self._timer is not None:
            self._timer.stop()

    @property
    def walking(self) -> bool:
        return self._anchor_px is not None

    # ---- One step -------------------------------------------------------------
    def _tick(self) -> None:
        vp = self._viewport
        if vp is None or self._anchor_px is None or self._cursor_px is None:
            return
        from PySide6.QtWidgets import QApplication
        mods = QApplication.keyboardModifiers() | self._modifiers
        dx = self._cursor_px.x() - self._anchor_px.x()
        dy = self._anchor_px.y() - self._cursor_px.y()      # up = forward
        self.step(vp, dx, dy, self.TICK_MS / 1000.0, mods)
        emit = getattr(vp, "measurementChanged", None)
        if emit is not None and hasattr(vp, "_measurement_text"):
            emit.emit(vp._measurement_text())
        vp.update()

    def step(self, viewport, dx: float, dy: float, dt: float,
             modifiers=Qt.NoModifier) -> None:
        """One walking step for a cursor ``(dx, dy)`` pixels from the
        crosshair (``dy`` up), ``dt`` seconds long. Pure of the timer, so
        a test can walk deterministically."""
        cam = viewport.camera
        h = eye_height()

        def gain(px: float) -> float:
            if abs(px) < self.DEAD_PX:
                return 0.0
            return max(-1.0, min(1.0, px / self.FULL_PX))

        speed = self.WALK_SPEED * (self.RUN_FACTOR
                                   if modifiers & Qt.ControlModifier else 1.0)
        eye = cam.eye()
        forward = _level_heading(cam)
        right = QVector3D.crossProduct(forward, _UP).normalized()
        through_walls = bool(modifiers & Qt.AltModifier)
        if modifiers & Qt.ShiftModifier:
            # Up/down and sideways, no turning, no floor to follow.
            delta = right * (gain(dx) * speed * dt) + _UP * (gain(dy) * speed * dt)
            if delta.lengthSquared() < 1e-18:
                return
            if not through_walls and self._blocked(viewport, eye, delta, h):
                return
            cam.move_eye(delta)
            return
        turn = gain(dx) * self.TURN_DEG_PER_S * dt
        if abs(turn) > 1e-9:
            cam.turn(turn, 0.0)
            forward = _level_heading(cam)
        advance = gain(dy) * speed * dt
        if abs(advance) < 1e-12:
            return
        delta = forward * advance
        if not through_walls and self._blocked(viewport, eye, delta, h):
            return
        cam.move_eye(delta)
        if not through_walls:
            self._follow_floor(viewport, h)

    def _blocked(self, viewport, eye: QVector3D, delta: QVector3D,
                 h: float) -> bool:
        """Would this step run into a wall? Two feelers along the step, at
        eye height and at knee height, must both be clear for the step
        plus the clearance."""
        dist = getattr(viewport, "ray_distance", None)
        if dist is None:
            return False
        d = QVector3D(delta)
        length = d.length()
        if length < 1e-12:
            return False
        d = d / length
        reach = length + self.CLEARANCE
        for origin in (eye, eye - _UP * max(h - self.KNEE, 0.0)):
            t = dist(origin, d)
            if t is not None and t < reach:
                return True
        return False

    def _follow_floor(self, viewport, h: float) -> None:
        """Keep the eye ``h`` above whatever is underfoot: a stair riser
        no taller than STEP_UP is climbed, a drop is fallen, and with
        nothing below the ground plane (z = 0) is the floor."""
        cam = viewport.camera
        eye = cam.eye()
        # Look down from just above the tallest step the feet can take, so a
        # riser ahead is seen as the new floor rather than as a wall.
        z_from = eye.z() - h + self.STEP_UP
        floor = _floor_below(viewport, eye.x(), eye.y(), z_from)
        if floor is None:
            floor = min(0.0, eye.z() - h)
        target_z = floor + h
        if abs(target_z - eye.z()) > 1e-6:
            cam.move_eye(_UP * (target_z - eye.z()))

    # ---- Overlay ----------------------------------------------------------------
    def draw_overlay(self, viewport, painter) -> None:
        """SketchUp's crosshair where the walk began."""
        if self._anchor_px is None:
            return
        from PySide6.QtGui import QColor, QPen
        x, y = self._anchor_px.x(), self._anchor_px.y()
        painter.setPen(QPen(QColor(30, 30, 30, 230), 1.5))
        painter.drawLine(QPointF(x - 10, y), QPointF(x + 10, y))
        painter.drawLine(QPointF(x, y - 10), QPointF(x, y + 10))
        painter.setPen(QPen(QColor(255, 255, 255, 200), 1.0))
        painter.drawEllipse(QPointF(x, y), 4.0, 4.0)
