# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""Tape Measure tool (T): measure distances and place construction guides.

SketchUp behaviour, two modes decided by what the first click lands on:

- **From an edge's body** → dragging pulls out an infinite **guide line**
  parallel to that edge, at the dragged (or VCB-typed) offset. This is the
  alignment workflow: pull a guide 2.5 m off a wall, then draw against it.
  A **guide line's body** works the same way (SketchUp; issue #22): pull a
  second guide 2 m off the first, and so on across a whole grid.
- **From a point** (endpoint, corner, free space) → the second click just
  **measures**: the distance shows live at the cursor and in the status bar,
  and stays in the measurements box. No geometry is created.

Guides are scaffolding (``Scene.guides``): dashed overlay lines the snap engine
locks onto, erasable with the Eraser or Edit ▸ Delete Guides. Esc cancels.
"""
from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QVector3D

from core.guide import Guide
from core.history import AddGuideCommand
from core.i18n import tr
from tools.base import Tool, ToolContext


class TapeMeasureTool(Tool):
    name = "Tape Measure"
    shortcut = "T"
    vcb_label = "Distance"

    def __init__(self) -> None:
        self.start_point: QVector3D | None = None
        self.hover_point: QVector3D | None = None
        self.chain_first_point: QVector3D | None = None  # silence close-snap
        self.work_plane: tuple | None = None
        self._edge = None            # source edge → guide-line mode
        self._measured: float | None = None
        #: SketchUp's Ctrl on the Tape: with guides OFF the tool only
        #: measures, and clicking an edge's body no longer leaves a guide
        #: behind (issue #29, @pacaeiro). Survives between operations, like
        #: SketchUp's — it is a mode, not a per-click modifier.
        self._guides = True

    # ---- Lifecycle ----------------------------------------------------------
    def on_activate(self, viewport) -> None:
        self._reset()

    def on_deactivate(self, viewport) -> None:
        self._reset()
        self.hover_point = None

    # ---- Keyboard -----------------------------------------------------------
    def on_key(self, viewport, key: int, modifiers) -> bool:
        # Ctrl toggles guide creation (SketchUp: the Tape either measures or
        # leaves a guide, and the cursor shows a + when it will).
        if key == Qt.Key_Control:
            self._guides = not self._guides
            viewport.flash_status(tr("Create guides: on") if self._guides
                                  else tr("Create guides: off — measure only"))
            viewport.update()
            return True
        return super().on_key(viewport, key, modifiers)

    # ---- Spatial input ------------------------------------------------------
    def on_click(self, ctx: ToolContext) -> None:
        viewport = ctx.viewport
        if self.start_point is None:
            self.start_point = ctx.world
            # Clicking an edge's BODY starts guide mode; an endpoint measures.
            kind = ctx.snap.kind if ctx.snap is not None else "none"
            # pick_edge_ANY, not pick_edge: the plain one only ever sees
            # the loose mesh, so a click on a component's edge found
            # nothing and fell through to plain measuring (issue #28,
            # @pacaeiro). SketchUp reads a group's edges from outside
            # without opening it, and so does the rest of IngeTrazo — this
            # is the same picker the Down-arrow reference lock uses, which
            # hands a group's edge back as a world pseudo-edge.
            pick_any = getattr(viewport, "pick_edge_any", None)
            edge = (pick_any(ctx.screen.x(), ctx.screen.y()) if pick_any
                    else viewport.pick_edge(ctx.screen.x(), ctx.screen.y()))
            if edge is None:
                # A guide LINE is a source too (a ``Guide`` exposes the same
                # ``.a``/``.b`` span as an edge): guides pulled from guides
                # are how a grid is laid out (issue #22, @pacaeiro).
                pick = getattr(viewport, "pick_guide", None)
                g = pick(ctx.screen.x(), ctx.screen.y()) if pick else None
                if g is not None and getattr(g, "is_line", False):
                    edge = g
            self._edge = edge if (self._guides and edge is not None
                                  and kind not in ("endpoint", "midpoint",
                                                   "close", "origin",
                                                   "intersection")) else None
            return
        if self._edge is not None:
            offset = self._guide_offset(ctx.world)
            if offset is not None and offset.length() > 1e-9:
                self._place_guide(viewport, offset)
        else:
            dist = (ctx.world - self.start_point).length()
            self._measured = dist
            viewport.flash_status(
                tr("Distance: {d} m").format(d=f"{dist:.3f}"), 4000)
        self._reset()
        viewport.update()

    def on_hover(self, ctx: ToolContext) -> None:
        self.hover_point = ctx.world
        ctx.viewport.update()

    def on_value(self, viewport, value) -> bool:
        """Typing a distance in guide mode places the guide exactly there."""
        if (self.start_point is None or self._edge is None
                or isinstance(value, tuple) or self.hover_point is None):
            return False
        offset = self._guide_offset(self.hover_point)
        if offset is None or offset.length() < 1e-9:
            return False
        self._place_guide(viewport, offset.normalized() * float(value))
        self._reset()
        viewport.update()
        return True

    def on_cancel(self, viewport) -> None:
        self._reset()
        viewport.update()

    # ---- Preview ------------------------------------------------------------
    def rubber_band_lines(self):
        if self.start_point is None or self.hover_point is None:
            return []
        if self._edge is not None:
            offset = self._guide_offset(self.hover_point)
            if offset is not None:
                g = Guide(self.start_point + offset, self._edge_dir())
                return [g.segment(), (self.start_point, self.start_point + offset)]
        return [(self.start_point, self.hover_point)]

    def value_label(self):
        if self.start_point is None or self.hover_point is None:
            return None
        if self._edge is not None:
            offset = self._guide_offset(self.hover_point)
            d = offset.length() if offset is not None else 0.0
        else:
            d = (self.hover_point - self.start_point).length()
        mid = (self.start_point + self.hover_point) * 0.5
        return (f"{d:.2f} m", mid)

    # ---- Internals ----------------------------------------------------------
    def _edge_dir(self) -> QVector3D:
        return (self._edge.b - self._edge.a).normalized()

    def _guide_offset(self, world: QVector3D) -> QVector3D | None:
        """Cursor offset perpendicular to the source edge (the guide's pull)."""
        if self._edge is None or self.start_point is None:
            return None
        d = self._edge_dir()
        delta = world - self.start_point
        return delta - d * QVector3D.dotProduct(delta, d)

    def _place_guide(self, viewport, offset: QVector3D) -> None:
        guide = Guide(self.start_point + offset, self._edge_dir())
        viewport.history.execute(AddGuideCommand(guide))
        viewport.flash_status(
            tr("Guide at {d} m").format(d=f"{offset.length():.3f}"), 3000)

    def _reset(self) -> None:
        self.start_point = None
        self._edge = None
        self.work_plane = None
