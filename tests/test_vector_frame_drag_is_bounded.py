# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""El parpadeo al mover una vista en vectorial — Fase 10 (Rafael, 35:20).

    «Es que ahora mismo trato de mover y como que parpadea la ventana. No
    sé si es problema de mi gráfica o algún gazapo que tenéis por ahí.»

It was not his card, and Marco read the cause right: «cuando pones
vectorial la gráfica trabaja más». A vector frame inks every visible edge
of the model one QLineF at a time on every repaint — measured on a
200×140 mm frame of 20 000 segments at 4 px/mm, 120 ms, and 351 ms at
60 000. Dragging repainted all of it per mouse move.

The device cache the items already keep cannot fix it: Qt re-renders a
DeviceCoordinateCache whenever the item's device position moves by a
fraction of a pixel, and measured, a cached frame still repainted on half
the moves. So a drag draws the SILHOUETTE instead — cut lines and profiles
first, plain edges until a fixed budget runs out — the same trick the 3D
viewport uses while you orbit. Measured over eight moves: 661 → 122 ms at
3 px/mm, 610 → 70 at 6, 968 → 165 at 10.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import numpy as np
import pytest
from PySide6.QtCore import QEvent, QPointF, Qt
from PySide6.QtGui import QColor, QImage, QPainter
from PySide6.QtWidgets import QGraphicsSceneMouseEvent

from core.composition import MarcoVista
from core.hlr import KIND_CUT, KIND_EDGE, KIND_PROFILE


def _ev(kind):
    e = QGraphicsSceneMouseEvent(kind)
    e.setPos(QPointF(20.0, 20.0))
    e.setButton(Qt.LeftButton)
    e.setButtons(Qt.LeftButton)
    return e


def test_the_drag_flag_goes_on_for_every_selected_frame_and_off_after(
        monkeypatch):
    """Dragging a selection moves them all, and only the pressed item gets
    the mouse events."""
    from views.composer import ComposerWindow, FrameItem
    from views.main_window import MainWindow
    monkeypatch.setattr(ComposerWindow, "render_frame", lambda self, f: None)
    win = MainWindow()
    comp = None
    try:
        comp = ComposerWindow(win)
        comp.comp.frames.append(MarcoVista(x_mm=20.0, y_mm=140.0, w_mm=80.0,
                                           h_mm=60.0, style="vectorial"))
        comp._rebuild_canvas()
        frames = [it for it in comp.canvas.items()
                  if isinstance(it, FrameItem)]
        assert len(frames) == 2
        assert not any(it._dragging for it in frames)
        for it in frames:
            it.setSelected(True)

        frames[0].mousePressEvent(_ev(QEvent.GraphicsSceneMousePress))
        assert all(it._dragging for it in frames)
        frames[0].mouseReleaseEvent(_ev(QEvent.GraphicsSceneMouseRelease))
        assert not any(it._dragging for it in frames)
    finally:
        if comp is not None:
            comp.close()
        win._saved_version = win.viewport.scene.version
        win.close()


def _lines_drawn(segs, kinds, budget):
    """How many QLineF the vector pass actually inks, by class."""
    from views.composer import _paint_hlr_lines_mm
    frame = MarcoVista(style="vectorial", w_mm=100.0, h_mm=100.0)
    img = QImage(50, 50, QImage.Format_RGB32)
    img.fill(QColor(255, 255, 255))
    p = QPainter(img)
    seen = {}
    real = p.drawLines

    def spy(lines):
        seen[p.pen().widthF()] = seen.get(p.pen().widthF(), 0) + len(lines)
        real(lines)

    p.drawLines = spy
    _paint_hlr_lines_mm(p, frame, segs, kinds, budget)
    p.end()
    return seen


def test_the_budget_keeps_the_silhouette_and_drops_plain_edges():
    """Cut lines and profiles are what say where the drawing IS; those go
    in first, and the plain edges take what is left."""
    n_edge, n_prof, n_cut = 5000, 40, 25
    total = n_edge + n_prof + n_cut
    rng = np.random.default_rng(11)
    segs = rng.uniform(0.0, 100.0, (total, 4))
    kinds = np.concatenate([
        np.full(n_edge, KIND_EDGE, dtype=np.int8),
        np.full(n_prof, KIND_PROFILE, dtype=np.int8),
        np.full(n_cut, KIND_CUT, dtype=np.int8)])

    # pens: edge 0.18, profile 0.35, cut 0.5 mm — they tell the classes apart
    full = _lines_drawn(segs, kinds, None)
    assert sum(full.values()) == total                  # everything, normally

    drag = _lines_drawn(segs, kinds, 300)
    assert sum(drag.values()) == 300                    # bounded
    assert drag[0.5] == n_cut                           # every cut line
    assert drag[0.35] == n_prof                         # every profile
    assert drag[0.18] == 300 - n_cut - n_prof           # edges fill the rest


def test_a_drawing_under_the_budget_is_untouched():
    rng = np.random.default_rng(12)
    segs = rng.uniform(0.0, 100.0, (120, 4))
    kinds = np.full(120, KIND_EDGE, dtype=np.int8)
    assert sum(_lines_drawn(segs, kinds, 3000).values()) == 120


def test_print_and_export_never_get_a_budget():
    """A sheet on paper is the deliverable: it always inks everything."""
    import inspect
    from views import composer
    sig = inspect.signature(composer.paint_frame_mm)
    assert sig.parameters["budget"].default is None
    src = inspect.getsource(composer.ComposerWindow._paint_sheet)
    assert "paint_frame_mm(" in src and "budget" not in src
    assert "paint_frame_mm(" in src and "budget" not in src
