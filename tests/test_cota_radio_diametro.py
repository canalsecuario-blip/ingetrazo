# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""Cota de radio y de diámetro — Fase 9 (Rafael).

He asked for the radius right after we shipped Fillet — «ya que pusisteis
el redondeo, pues sería lo suyo» (revisión 2, 42:40) — and his video on
drafting standards adds the diameter and the rules both obey, drawn case
by case on the AutoCAD sheet of `rafael-cotas/fotogramas/f1230.jpg`:

  8  the diameter's line passes through the centre
  9  it all fits inside → inside, arrows out at the arc
  10 it does not → arrows and words outside, and the line is prolonged
  12 the radius always starts AT the centre, text above, with its symbol
  13 changing quadrant must not leave the text upside down
  14 a radius that does not fit: out, arrow back at the centre, text above
  15 forbidden: an arrow pointing outwards on a leader that stops short of
     the centre, and text + arrow with no extension to the centre
  16 an arc is dimensioned exactly like a circle
"""
from __future__ import annotations

import math
import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest

from core.composition import CotaRadialItem, readable_deg


def _r(**kw) -> CotaRadialItem:
    base = dict(x_mm=100.0, y_mm=80.0, radius_mm=20.0, angle_deg=-30.0,
                scale_n=50.0, text_mm=2.5)
    base.update(kw)
    return CotaRadialItem(**base)


# ---- what the label says --------------------------------------------------

def test_the_symbol_goes_with_the_value():
    assert _r().label() == "R1.00 m"                    # 20 mm at 1:50
    assert _r(kind="diameter").label() == "Ø2.00 m"
    assert _r(text="<> (typ.)").label() == "R1.00 m (typ.)"


def test_a_diameter_measures_twice_the_radius():
    a = _r()
    b = _r(kind="diameter")
    assert b.measured_mm() == pytest.approx(2 * a.measured_mm())
    assert b.real_distance_m() == pytest.approx(2.0)


# ---- rules 8, 12, 15, 16: the line reaches the centre --------------------

def test_a_radius_starts_at_the_centre():
    (ax, ay), (bx, by) = _r().line_points()
    assert (ax, ay) == (0.0, 0.0)                       # the centre itself
    assert math.hypot(bx, by) == pytest.approx(20.0)    # out to the arc


def test_a_diameter_runs_right_through_the_centre():
    (ax, ay), (bx, by) = _r(kind="diameter").line_points()
    assert (ax + bx, ay + by) == pytest.approx((0.0, 0.0))   # symmetric
    assert math.hypot(bx - ax, by - ay) == pytest.approx(40.0)


@pytest.mark.parametrize("deg", [0.0, -30.0, 90.0, 140.0, -170.0, 45.0])
def test_the_line_leaves_the_centre_in_any_direction_asked(deg):
    """Rule 12: «siempre parte del centro, en la dirección que se quiera»."""
    (ax, ay), (bx, by) = _r(angle_deg=deg).line_points()
    assert (ax, ay) == (0.0, 0.0)
    assert math.degrees(math.atan2(by, bx)) == pytest.approx(deg, abs=1e-9)


# ---- rules 9, 10, 14: inside while it fits, outside when it does not -----

def test_a_big_circle_keeps_the_words_inside():
    ct = _r(radius_mm=40.0)
    assert not ct.outside()
    lx, ly = ct.text_anchor()
    assert math.hypot(lx, ly) < ct.radius_mm            # over the line
    assert ct.tail_end() == pytest.approx(ct.line_points()[1])


def test_a_small_one_takes_them_out_and_prolongs_the_line():
    ct = _r(radius_mm=3.0)
    assert ct.outside()
    lx, ly = ct.text_anchor()
    assert math.hypot(lx, ly) > ct.radius_mm            # past the arc
    tail = math.hypot(*ct.tail_end())
    assert tail > ct.radius_mm                          # «la línea se prolonga»
    assert tail >= math.hypot(lx, ly)                   # and carries the words


@pytest.mark.parametrize("deg", [-30.0, 150.0, 0.0, 180.0, 60.0, -120.0])
def test_a_diameters_words_keep_off_the_centre_mark_on_the_right(deg):
    """Rule 3's reason: the centre belongs to the axes, and «un número
    encima de un eje se lee mal, sobre todo la coma». The Ø41,96 of the
    reference sheet sits in the outer half — and Marco fixed WHICH half
    (2026-09-20): the right-hand one, «no al medio porque se cruzaría con
    otras líneas de dibujo que salen del radio», whichever way the line
    was drawn."""
    ct = _r(kind="diameter", radius_mm=40.0, angle_deg=deg)
    assert not ct.outside()
    lx, ly = ct.text_anchor()
    assert math.hypot(lx, ly) == pytest.approx(20.0)     # half the radius
    assert lx > 0                                        # the right-hand half


def test_a_vertical_diameters_words_sit_on_its_top_half():
    """A vertical diameter's text reads bottom-to-top, so its «right» is
    the top of the page (y grows downward)."""
    for deg in (90.0, -90.0):
        lx, ly = _r(kind="diameter", radius_mm=40.0,
                    angle_deg=deg).text_anchor()
        assert abs(lx) < 1e-9 and ly < 0


def test_the_drafter_can_force_it_either_way():
    assert _r(radius_mm=3.0, placement="in").outside() is False
    assert _r(radius_mm=40.0, placement="out").outside() is True


# ---- rule 13: the text never ends up upside down -------------------------

@pytest.mark.parametrize("deg", [0.0, 30.0, 89.0, 91.0, 150.0, -150.0,
                                 -91.0, -89.0, 179.0])
def test_whatever_quadrant_it_is_in_the_text_stays_readable(deg):
    ct = _r(angle_deg=deg)
    ux, uy = ct.heading()
    turn = readable_deg(ux, uy)
    assert -90.0 <= turn < 90.0


# ---- it survives the file ------------------------------------------------

def test_it_travels_in_the_sheet_and_an_older_one_simply_has_none():
    from core.composition import Composicion
    c = Composicion()
    c.cotas_rad.append(_r(kind="diameter", radius_mm=7.0))
    back = Composicion.from_dict(c.to_dict())
    assert len(back.cotas_rad) == 1
    assert back.cotas_rad[0].kind == "diameter"
    assert back.cotas_rad[0].label() == "Ø0.70 m"
    assert Composicion.from_dict({}).cotas_rad == []
    # and it is one of the sheet's items, so z-order, groups, lock and
    # delete reach it like everything else
    assert back.cotas_rad[0] in back.all_items()


# ---- and the tool places it ----------------------------------------------

def test_two_clicks_place_it_and_ctrl_makes_it_a_diameter(monkeypatch):
    from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
    from PySide6.QtGui import QMouseEvent
    from views.composer import ComposerWindow
    from views.main_window import MainWindow
    monkeypatch.setattr(ComposerWindow, "render_frame", lambda self, f: None)
    win = MainWindow()
    comp = None
    try:
        comp = ComposerWindow(win)
        view = comp._view
        comp.tool_mode = "cota_radio"

        def click(x_mm, y_mm, mods=Qt.NoModifier):
            px = view.mapFromScene(QPointF(x_mm, y_mm))
            view.mousePressEvent(QMouseEvent(
                QEvent.MouseButtonPress, QPointF(px),
                view.mapToGlobal(QPoint(px)),
                Qt.LeftButton, Qt.LeftButton, mods))

        click(60.0, 60.0)                       # the centre
        assert view._rad_centre is not None
        assert not comp.comp.cotas_rad
        click(90.0, 60.0)                       # a point on the arc
        assert len(comp.comp.cotas_rad) == 1
        ct = comp.comp.cotas_rad[0]
        assert ct.kind == "radius"
        assert (ct.x_mm, ct.y_mm) == pytest.approx((60.0, 60.0))
        assert ct.radius_mm == pytest.approx(30.0)
        assert ct.angle_deg == pytest.approx(0.0)
        assert view._rad_centre is None         # ready for the next one

        comp.tool_mode = "cota_radio"
        click(60.0, 120.0)
        click(60.0, 140.0, Qt.ControlModifier)
        assert comp.comp.cotas_rad[-1].kind == "diameter"
        # undo removes it, like every other item
        assert comp.history.undo()
        assert len(comp.comp.cotas_rad) == 1
    finally:
        if comp is not None:
            comp.close()
        win._saved_version = win.viewport.scene.version
        win.close()


# ---- the angular dimension finally snaps, and Shift gives an exact 90° ---

def test_the_angular_dimension_snaps_to_the_drawing(monkeypatch):
    """«No engancha a nada, no hay manera de poner 90°» (29:20). The tool
    asked for a snapped point and was never on the list of tools that get
    one, so it always got the raw cursor back."""
    from views.composer import ComposerCanvasView
    assert "cota_ang" in ComposerCanvasView._GEOM_SNAP_TOOLS
    assert "cota_radio" in ComposerCanvasView._GEOM_SNAP_TOOLS


def test_shift_puts_an_arm_on_an_exact_fifteen_degrees(monkeypatch):
    from PySide6.QtCore import QPointF, Qt
    from views.composer import ComposerWindow
    from views.main_window import MainWindow
    monkeypatch.setattr(ComposerWindow, "render_frame", lambda self, f: None)
    win = MainWindow()
    comp = None
    try:
        comp = ComposerWindow(win)
        view = comp._view
        view._ang_pts = [(50.0, 50.0)]                  # the vertex
        # first arm: off the page horizontal
        free = QPointF(50.0 + 40.0, 50.0 - 3.0)         # ≈ -4.3°
        assert view._ang_step(free, Qt.NoModifier) == free
        snapped = view._ang_step(free, Qt.ShiftModifier)
        deg = math.degrees(math.atan2(snapped.y() - 50.0, snapped.x() - 50.0))
        assert deg == pytest.approx(0.0, abs=1e-9)
        assert math.hypot(snapped.x() - 50.0,
                          snapped.y() - 50.0) == pytest.approx(
                              math.hypot(40.0, 3.0))    # same distance
        # second arm: off the FIRST one, so the SWEEP is the round number
        view._ang_pts.append((50.0 + 40.0, 50.0))       # arm 1 along +x
        rough = QPointF(50.0 + 2.0, 50.0 - 40.0)        # ≈ 87° up from it
        exact = view._ang_step(rough, Qt.ShiftModifier)
        sweep = math.degrees(math.atan2(exact.y() - 50.0, exact.x() - 50.0))
        assert sweep == pytest.approx(-90.0, abs=1e-9)  # a square corner
    finally:
        if comp is not None:
            comp.close()
        win._saved_version = win.viewport.scene.version
        win.close()


# ---- the level mark reads its own height --------------------------------

def test_a_level_mark_on_an_elevation_knows_its_height(monkeypatch):
    """«¿Sería posible que detectase la altura? Sería un puntazo para no
    tener tú que anotarlo» (21:20). In an elevation the page's rows ARE the
    model's heights, so even a click that snapped to nothing knows."""
    from PySide6.QtGui import QVector3D
    from views.composer import ComposerWindow
    from views.main_window import MainWindow
    monkeypatch.setattr(ComposerWindow, "render_frame", lambda self, f: None)
    win = MainWindow()
    comp = None
    try:
        comp = ComposerWindow(win)
        scene = win.viewport.scene
        scene.mesh.add_face([QVector3D(-2, 0, 0), QVector3D(2, 0, 0),
                             QVector3D(2, 0, 3), QVector3D(-2, 0, 3)])
        scene.version += 1
        f = comp.comp.frames[0]
        f.view_key, f.style = "std:front", "vectorial"
        f.x_mm, f.y_mm, f.w_mm, f.h_mm, f.scale_n = 20.0, 20.0, 160.0, 80.0, 50.0
        # 80 mm of paper at 1:50 = 4 m of model, centred on the wall
        top = comp.frame_level_at(f, 100.0, f.y_mm)
        mid = comp.frame_level_at(f, 100.0, f.y_mm + f.h_mm / 2)
        assert top is not None
        assert top - mid == pytest.approx(2.0)          # half of 4 m
        # 1 mm of paper is 0.05 m of model, and it is linear
        one_mm = comp.frame_level_at(f, 100.0, f.y_mm + 1.0)
        assert top - one_mm == pytest.approx(0.05)
        # a PLAN cannot tell, and says so instead of guessing
        f.view_key = "std:top"
        assert comp.frame_level_at(f, 100.0, 60.0) is None

        # …and placing one on the elevation writes the height it found
        f.view_key = "std:front"
        comp.tool_mode = "nivel"
        comp.place_tool(100.0, f.y_mm + 20.0, 100.0, f.y_mm + 20.0)
        mark = comp.comp.niveles[-1]
        assert mark.level_m() == pytest.approx(
            comp.frame_level_at(f, 100.0, f.y_mm + 20.0))
        assert abs(mark.level_m()) > 0.1                 # not the old 0.00
    finally:
        if comp is not None:
            comp.close()
        win._saved_version = win.viewport.scene.version
        win.close()
