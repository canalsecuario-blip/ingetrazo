# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""Change Axes (issue #44, @pacaeiro): give a group or component new local
axes, SketchUp's way — right-click ▸ Change Axes, then three clicks:

1. the new ORIGIN,
2. a point along the new RED axis,
3. a point giving the GREEN direction (squared to red on the way; blue is
   what is left, right-handed).

Nothing moves in the world: a group only takes the new frame; a component
re-expresses its shared definition so every copy carries the new axes and
stays where it is (``core.history.ChangeAxesCommand``). The clicks snap like
any drawing tool — an endpoint, an edge, an axis inference from the origin —
which is how you line the axes up with the geometry you meant.
"""
from __future__ import annotations

from PySide6.QtGui import QVector3D

from core.i18n import tr
from tools.base import Tool, ToolContext


class ChangeAxesTool(Tool):
    name = "Change Axes"
    uses_snap = True

    def __init__(self) -> None:
        #: The group or component whose axes change — set by whoever
        #: activates the tool (the context menu).
        self.target = None
        self.start_point: QVector3D | None = None     # the new origin
        self.red_point: QVector3D | None = None
        self.hover_point: QVector3D | None = None

    # ---- Lifecycle ----------------------------------------------------------
    def on_activate(self, viewport) -> None:
        self.start_point = self.red_point = self.hover_point = None
        if self.target is None:
            viewport.flash_status(tr("Select one group or component first"))

    def on_deactivate(self, viewport) -> None:
        self.start_point = self.red_point = self.hover_point = None

    def on_cancel(self, viewport) -> None:
        self.start_point = self.red_point = None
        viewport.update()

    # ---- Input --------------------------------------------------------------
    def on_hover(self, ctx: ToolContext) -> None:
        self.hover_point = QVector3D(ctx.world)
        ctx.viewport.update()

    def on_click(self, ctx: ToolContext) -> None:
        vp = ctx.viewport
        if self.target is None:
            return
        p = QVector3D(ctx.world)
        if self.start_point is None:
            self.start_point = p
            vp.flash_status(tr("Click along the new red axis"))
            return
        if self.red_point is None:
            if (p - self.start_point).length() < 1e-6:
                return
            self.red_point = p
            vp.flash_status(tr("Click to set the green direction"))
            return
        frame = self._frame(p)
        if frame is None:
            vp.flash_status(tr("The green direction cannot run along red — "
                               "click off the red axis"), 4000)
            return
        from core.history import ChangeAxesCommand
        vp.history.execute(ChangeAxesCommand(self.target, frame))
        vp.flash_status(tr("Axes changed"), 2500)
        self.target = None
        self.start_point = self.red_point = None
        win = vp.window() if hasattr(vp, "window") else None
        back = getattr(win, "_activate_tool", None)
        if callable(back):
            back("select")
        vp.update()

    # ---- Geometry -----------------------------------------------------------
    def _axes(self, green_at: QVector3D | None):
        """``(x, y, z)`` for the clicks so far and a green point, or
        ``None`` when they do not make a frame."""
        if self.start_point is None or self.red_point is None:
            return None
        x = self.red_point - self.start_point
        if x.length() < 1e-9:
            return None
        x = x.normalized()
        if green_at is None:
            return None
        g = green_at - self.start_point
        y = g - x * QVector3D.dotProduct(g, x)
        if y.length() < 1e-6:
            return None
        y = y.normalized()
        z = QVector3D.crossProduct(x, y).normalized()
        return x, y, z

    def _frame(self, green_at: QVector3D):
        axes = self._axes(green_at)
        if axes is None:
            return None
        from core.axes import frame_matrix
        return frame_matrix(self.start_point, *axes)

    # ---- Preview ------------------------------------------------------------
    def rubber_band_lines(self):
        if self.start_point is None or self.hover_point is None:
            return []
        o = self.start_point
        if self.red_point is None:
            return [(o, self.hover_point)]
        axes = self._axes(self.hover_point)
        if axes is None:
            return [(o, self.red_point)]
        length = max((self.red_point - o).length(), 0.5)
        x, y, z = axes
        return [(o, o + x * length), (o, o + y * length),
                (o, o + z * length)]

    def value_label(self):
        if self.start_point is None or self.hover_point is None:
            return None
        text = (tr("Red axis") if self.red_point is None
                else tr("Green axis"))
        return (text, self.hover_point)
