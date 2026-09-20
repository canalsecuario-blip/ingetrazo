# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""Cota forzada recta — Fase 8 de la revisión de Rafael (41:30–43:00).

    «Si el punto a acotar no está perfectamente alineado con el otro… yo
    quiero acotar de aquí a aquí arriba, pero no tengo un punto
    perfectamente alineado con este que coincida. ¿Veis cómo queda la cota
    inclinada? La cota no puede quedar inclinada si estás acotando algo en
    vertical.»

Shift used to drag the second POINT onto an axis, which is the wrong cure:
it throws away the snap to the point he actually wants — «el problema es
que aquí me cogen muchos puntos, no me coge el punto final así como así» —
and leaves the number to the eye, «software técnico: a ojo no». What a
drafter wants is AutoCAD's DIMLINEAR: keep both points, measure only their
horizontal or vertical separation, and draw the line straight with
extension lines of different lengths.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from core.composition import CotaItem, cota_line_deg


# Two points that are NOT aligned: 30 mm across, 40 mm up the page.
def _slanted(**kw) -> CotaItem:
    return CotaItem(x_mm=20.0, y_mm=80.0, dx_mm=30.0, dy_mm=-40.0,
                    sep_mm=12.0, scale_n=50.0, **kw)


def test_aligned_is_still_the_slanted_cota_of_before():
    ct = _slanted()
    (a2x, a2y), (b2x, b2y) = ct.line_points()
    assert (b2x - a2x, b2y - a2y) == pytest.approx((30.0, -40.0))
    assert ct.measured_mm() == pytest.approx(50.0)       # the hypotenuse
    assert ct.label() == "2.50 m"


def test_forced_vertical_measures_the_height_and_draws_straight():
    ct = _slanted(axis="v")
    (a2x, a2y), (b2x, b2y) = ct.line_points()
    assert a2x == pytest.approx(b2x)                     # a vertical line
    assert (b2y - a2y) == pytest.approx(-40.0)
    assert ct.measured_mm() == pytest.approx(40.0)
    assert ct.label() == "2.00 m"                        # 40 mm at 1:50
    assert cota_line_deg(ct) == pytest.approx(-90.0)     # and it reads ISO


def test_forced_horizontal_measures_the_width():
    ct = _slanted(axis="h")
    (a2x, a2y), (b2x, b2y) = ct.line_points()
    assert a2y == pytest.approx(b2y)
    assert ct.measured_mm() == pytest.approx(30.0)
    assert ct.label() == "1.50 m"
    assert cota_line_deg(ct) == pytest.approx(0.0)


def test_the_two_extension_lines_have_DIFFERENT_lengths():
    """That is the whole point: each one reaches its own real point, so a
    cota over two points at different heights is straight anyway."""
    ct = _slanted(axis="v")
    (a2x, a2y), (b2x, b2y) = ct.line_points()
    from math import hypot
    first = hypot(a2x - 0.0, a2y - 0.0)
    second = hypot(b2x - ct.dx_mm, b2y - ct.dy_mm)
    assert first == pytest.approx(12.0)                  # the near point
    assert second == pytest.approx(18.0)                 # the far one
    assert abs(first - second) > 1.0


def test_an_older_sheet_opens_aligned_and_a_forced_one_survives_the_file():
    from core.composition import Composicion
    c = Composicion()
    c.cotas.append(_slanted(axis="v"))
    c.cotas.append(_slanted())
    back = Composicion.from_dict(c.to_dict())
    assert [x.axis for x in back.cotas] == ["v", ""]
    # a cota written before the field simply has none
    legacy = Composicion.from_dict(
        {"cotas": [{"x_mm": 1.0, "y_mm": 2.0, "dx_mm": 30.0, "dy_mm": 40.0}]})
    assert legacy.cotas[0].axis == ""
    assert legacy.cotas[0].measured_mm() == pytest.approx(50.0)


def test_the_label_and_the_hit_area_follow_the_forced_line(monkeypatch):
    from views.composer import (ComposerWindow, CotaCanvasItem,
                                cota_label_anchor)
    from views.main_window import MainWindow
    monkeypatch.setattr(ComposerWindow, "render_frame", lambda self, f: None)
    win = MainWindow()
    comp = None
    try:
        comp = ComposerWindow(win)
        ct = _slanted(axis="v")
        comp.comp.cotas.append(ct)
        comp._rebuild_canvas()
        item = next(it for it in comp.canvas.items()
                    if isinstance(it, CotaCanvasItem) and it.model is ct)
        # the label rides the middle of the DIMENSION line, not of the
        # slanted segment it measures
        lx, ly = cota_label_anchor(ct)
        assert lx == pytest.approx(ct.sep_mm)
        assert ly == pytest.approx(ct.dy_mm / 2)
        from PySide6.QtCore import QPointF
        shape = item.shape().translated(item.pos())
        on_line = QPointF(ct.x_mm + ct.sep_mm, ct.y_mm + ct.dy_mm / 2)
        assert shape.contains(on_line)
    finally:
        if comp is not None:
            comp.close()
        win._saved_version = win.viewport.scene.version
        win.close()


def test_the_panel_can_straighten_a_cota_already_drawn(monkeypatch):
    """The way back when Shift was let go a moment early — and the way to
    fix the nine sheets already drawn."""
    from views.composer import ComposerWindow, CotaCanvasItem
    from views.main_window import MainWindow
    monkeypatch.setattr(ComposerWindow, "render_frame", lambda self, f: None)
    win = MainWindow()
    comp = None
    try:
        comp = ComposerWindow(win)
        ct = _slanted()
        comp.comp.cotas.append(ct)
        comp._rebuild_canvas()
        item = next(it for it in comp.canvas.items()
                    if isinstance(it, CotaCanvasItem) and it.model is ct)
        assert ct.label() == "2.50 m"
        comp._panel_edit(item, {"axis": "v"})
        assert ct.axis == "v" and ct.label() == "2.00 m"
        comp.history.undo()
        assert ct.axis == "" and ct.label() == "2.50 m"
    finally:
        if comp is not None:
            comp.close()
        win._saved_version = win.viewport.scene.version
        win.close()


def test_a_forced_chain_puts_every_cota_on_ONE_line(monkeypatch):
    """The two asks of Fase 8 together: a chain of points at slightly
    different heights, forced horizontal, must come out as one straight
    row of cotas — «te lo acota a la altura» (Rafael, 27:00)."""
    from PySide6.QtCore import QPointF
    from views.composer import ComposerWindow
    from views.main_window import MainWindow
    monkeypatch.setattr(ComposerWindow, "render_frame", lambda self, f: None)
    win = MainWindow()
    comp = None
    try:
        comp = ComposerWindow(win)
        view = comp._view
        view._chain_axis = "h"
        # three points along a wall, none of them at the same height
        pts = [QPointF(20.0, 100.0), QPointF(60.0, 103.0), QPointF(95.0, 99.0)]
        view._chain_click(pts[0], None)
        view._chain_click(pts[1], None)
        view._chain_click(QPointF(60.0, 130.0), None)   # the offset row
        view._chain_click(pts[2], None)
        cotas = view._chain_cotas
        assert len(cotas) == 2
        rows = set()
        for ct in cotas:
            (a2x, a2y), (b2x, b2y) = ct.line_points()
            assert ct.axis == "h"
            assert a2y == pytest.approx(b2y)            # each one straight
            rows.add(round(ct.y_mm + a2y, 6))
        assert len(rows) == 1                           # …and all on one row
        assert rows.pop() == pytest.approx(130.0)
        # each measures only its horizontal step, not the slanted distance
        assert [round(c.measured_mm(), 6) for c in cotas] == [40.0, 35.0]
        view.finish_chain()
        total = comp.comp.cotas[-1]
        assert total.axis == "h"
        assert total.measured_mm() == pytest.approx(75.0)
    finally:
        if comp is not None:
            comp.close()
        win._saved_version = win.viewport.scene.version
        win.close()
