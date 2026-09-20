# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""Acotación desde línea base, y la regla 4 de la normativa.

Marco, 2026-09-19, after we closed the 0.4.7: «tal vez alguna como
dimensión alineada, otra [lineal] y otra dimcontinue». He was right that
the family is the way to read what Rafael wanted, and reading the video's
transcript settles which of them were missing: the standards video never
names a command, so DIMALIGNED / DIMLINEAR / DIMCONTINUE were already
there — and **DIMBASELINE was not**. It is the one that puts every
dimension from the SAME first point, each stacked a row further out,
which is how a plan carries accumulated distances off a corner.

Rule 4 of the standards video (08:00): «la línea de cota se prolonga
hasta cubrir todo el texto; si el texto crece, la línea crece». With the
text outside an end the line used to stop at the measured point and leave
the number floating beside it, which rule 6 calls «prohibido».
"""
from __future__ import annotations

import math
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtCore import QPointF

from core.composition import CotaItem


# ---- rule 4 -------------------------------------------------------------

def _ct(**kw) -> CotaItem:
    base = dict(x_mm=20.0, y_mm=40.0, dx_mm=30.0, dy_mm=0.0, sep_mm=0.0,
                scale_n=50.0, text_mm=3.0)
    base.update(kw)
    return CotaItem(**base)


def test_the_words_over_the_line_need_no_prolongation():
    assert _ct(text_along="middle").text_tail() is None


@pytest.mark.parametrize("along,side", [("end", 1.0), ("start", -1.0)])
def test_the_line_runs_on_under_words_placed_outside(along, side):
    ct = _ct(text_along=along)
    tail = ct.text_tail()
    assert tail is not None
    (ax, ay), (bx, by) = tail
    (l0x, l0y), (l1x, l1y) = ct.line_points()
    start = (l1x, l1y) if side > 0 else (l0x, l0y)
    assert (ax, ay) == pytest.approx(start)          # it leaves the line's end
    assert math.copysign(1.0, bx - ax) == side       # …going outwards
    # and it is long enough to run under the whole label
    assert abs(bx - ax) >= ct.label_extent_mm()


def test_if_the_text_grows_the_line_grows():
    """«Si el texto crece, la línea crece» — the reason it is measured
    from the label and not from a constant."""
    short = _ct(text_along="end", text="1")
    long = _ct(text_along="end", text="PROFUNDIDAD VARIABLE")
    a = short.text_tail()
    b = long.text_tail()
    assert abs(b[1][0] - b[0][0]) > abs(a[1][0] - a[0][0]) + 10.0


def test_a_hand_dragged_label_leaves_the_line_where_it_was():
    """LayOut lets the box be dragged anywhere and the line stays put;
    rule 4 is about the words sitting outside an END, not about a drag."""
    assert _ct(text_along="end", text_dx_mm=8.0).text_tail() is None


def test_a_vertical_cota_prolongs_along_ITS_line():
    ct = _ct(dx_mm=0.0, dy_mm=-30.0, text_along="end")
    (ax, ay), (bx, by) = ct.text_tail()
    assert ax == pytest.approx(bx)                   # straight up the page
    assert by < ay


def test_the_hit_area_covers_the_prolongation(monkeypatch):
    from views.composer import ComposerWindow, CotaCanvasItem
    from views.main_window import MainWindow
    monkeypatch.setattr(ComposerWindow, "render_frame", lambda self, f: None)
    win = MainWindow()
    comp = None
    try:
        comp = ComposerWindow(win)
        ct = _ct(text_along="end")
        comp.comp.cotas.append(ct)
        comp._rebuild_canvas()
        item = next(it for it in comp.canvas.items()
                    if isinstance(it, CotaCanvasItem) and it.model is ct)
        shape = item.shape().translated(item.pos())
        (_a, (bx, by)) = ct.text_tail()
        assert shape.contains(QPointF(ct.x_mm + bx - 1.0, ct.y_mm + by))
    finally:
        if comp is not None:
            comp.close()
        win._saved_version = win.viewport.scene.version
        win.close()


# ---- DIMBASELINE ---------------------------------------------------------

def _run(comp, tool, pts, offset):
    """Drive a chain / baseline run: two points, the offset, then the rest."""
    view = comp._view
    comp.tool_mode = tool
    view._chain_click(QPointF(*pts[0]), None)
    view._chain_click(QPointF(*pts[1]), None)
    view._chain_click(QPointF(*offset), None)
    for p in pts[2:]:
        view._chain_click(QPointF(*p), None)
    return view


def test_every_baseline_cota_starts_at_the_SAME_point(monkeypatch):
    from views.composer import ComposerWindow
    from views.main_window import MainWindow
    monkeypatch.setattr(ComposerWindow, "render_frame", lambda self, f: None)
    win = MainWindow()
    comp = None
    try:
        comp = ComposerWindow(win)
        view = _run(comp, "cota_base",
                    [(20.0, 100.0), (45.0, 100.0), (70.0, 100.0),
                     (110.0, 100.0)], (45.0, 120.0))
        cotas = view._chain_cotas
        assert len(cotas) == 3
        # all three measure FROM the base point…
        assert all((c.x_mm, c.y_mm) == pytest.approx((20.0, 100.0))
                   for c in cotas)
        # …and each one reaches further
        assert [round(c.dx_mm, 6) for c in cotas] == [25.0, 50.0, 90.0]
        assert [c.label() for c in cotas] == ["2.50 m", "5.00 m", "9.00 m"]
    finally:
        if comp is not None:
            comp.close()
        win._saved_version = win.viewport.scene.version
        win.close()


def test_the_baseline_cotas_stack_one_row_apart(monkeypatch):
    from views.composer import ComposerWindow
    from views.main_window import MainWindow
    monkeypatch.setattr(ComposerWindow, "render_frame", lambda self, f: None)
    win = MainWindow()
    comp = None
    try:
        comp = ComposerWindow(win)
        view = _run(comp, "cota_base",
                    [(20.0, 100.0), (45.0, 100.0), (70.0, 100.0),
                     (110.0, 100.0)], (45.0, 120.0))
        rows = [c.y_mm + c.line_points()[0][1] for c in view._chain_cotas]
        step = view._run_step_mm()
        assert rows[0] == pytest.approx(120.0)
        assert rows[1] - rows[0] == pytest.approx(step)
        assert rows[2] - rows[1] == pytest.approx(step)
    finally:
        if comp is not None:
            comp.close()
        win._saved_version = win.viewport.scene.version
        win.close()


def test_a_baseline_run_stacks_no_total(monkeypatch):
    """Its last cota already spans base → farthest point; a chain's does
    not, which is why only the chain gets one."""
    from views.composer import ComposerWindow
    from views.main_window import MainWindow
    monkeypatch.setattr(ComposerWindow, "render_frame", lambda self, f: None)
    win = MainWindow()
    comp = None
    try:
        comp = ComposerWindow(win)
        view = _run(comp, "cota_base",
                    [(20.0, 100.0), (45.0, 100.0), (70.0, 100.0)],
                    (45.0, 120.0))
        view.finish_chain()
        assert len(view._chain_cotas or []) == 0       # the run is over
        assert len(comp.comp.cotas) == 2               # no extra total
    finally:
        if comp is not None:
            comp.close()
        win._saved_version = win.viewport.scene.version
        win.close()


def test_the_chain_is_untouched_and_still_stacks_its_total(monkeypatch):
    """The two share one machine: prove the old one still behaves."""
    from views.composer import ComposerWindow
    from views.main_window import MainWindow
    monkeypatch.setattr(ComposerWindow, "render_frame", lambda self, f: None)
    win = MainWindow()
    comp = None
    try:
        comp = ComposerWindow(win)
        view = _run(comp, "cota_cadena",
                    [(20.0, 100.0), (45.0, 100.0), (70.0, 100.0)],
                    (45.0, 120.0))
        cotas = list(view._chain_cotas)
        assert len(cotas) == 2
        # each one starts where the last one ended
        assert (cotas[0].x_mm, cotas[1].x_mm) == pytest.approx((20.0, 45.0))
        assert [round(c.dx_mm, 6) for c in cotas] == [25.0, 25.0]
        # one line for all of them
        rows = {round(c.y_mm + c.line_points()[0][1], 6) for c in cotas}
        assert rows == {120.0}
        view.finish_chain()
        total = comp.comp.cotas[-1]
        assert total.measured_mm() == pytest.approx(50.0)   # and its total
    finally:
        if comp is not None:
            comp.close()
        win._saved_version = win.viewport.scene.version
        win.close()


def test_a_baseline_run_can_be_forced_straight(monkeypatch):
    """Shift belongs to the family too: points at different heights, one
    base, every cota straight and stacked."""
    from views.composer import ComposerWindow
    from views.main_window import MainWindow
    monkeypatch.setattr(ComposerWindow, "render_frame", lambda self, f: None)
    win = MainWindow()
    comp = None
    try:
        comp = ComposerWindow(win)
        comp._view._chain_axis = "h"
        view = _run(comp, "cota_base",
                    [(20.0, 100.0), (45.0, 103.0), (70.0, 98.0)],
                    (45.0, 125.0))
        cotas = view._chain_cotas
        assert all(c.axis == "h" for c in cotas)
        assert [round(c.measured_mm(), 6) for c in cotas] == [25.0, 50.0]
        rows = [c.y_mm + c.line_points()[0][1] for c in cotas]
        assert rows[1] - rows[0] == pytest.approx(view._run_step_mm())
    finally:
        if comp is not None:
            comp.close()
        win._saved_version = win.viewport.scene.version
        win.close()
