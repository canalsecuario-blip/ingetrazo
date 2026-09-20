# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""Los cinco pedidos de láminas — Fase 11, la última de la 0.4.7 (Rafael).

Small ones, and two of them turned out to be bugs rather than requests:
a typed ``10:1`` silently became ``1:1``, and a new view came up wearing
a deleted one's render because the caches are keyed on ``id(frame)``.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtGui import QVector3D

from core.composition import (Composicion, MarcoVista, format_scale,
                              parse_scale)


# ---- 1. enlargement scales, in the list and on the sheet ----------------

@pytest.mark.parametrize("n,shown", [
    (50, "1:50"), (100, "1:100"), (1, "1:1"),
    (0.5, "2:1"), (0.2, "5:1"), (0.1, "10:1"),
])
def test_an_enlargement_is_written_the_way_a_drawing_writes_it(n, shown):
    """«No me muestra la escala que yo le había metido, que era 10 a uno»
    (35:00). It used to print «ESC. 1:0.1»."""
    assert format_scale(n) == shown
    assert MarcoVista(scale_n=n).scale_label() == "ESC. " + shown


@pytest.mark.parametrize("text,n", [
    ("1:50", 50.0), ("50", 50.0), ("1:1", 1.0),
    ("10:1", 0.1), ("2:1", 0.5), ("1:0.1", 0.1),
    ("1:25,5", 25.5),                      # a comma is a decimal point here
])
def test_a_typed_scale_means_what_it_says(text, n):
    """Reading only what follows the colon turned a typed 10:1 into 1:1 —
    silently, on a technical drawing."""
    assert parse_scale(text) == pytest.approx(n)


def test_a_broken_scale_falls_back_instead_of_dividing_by_zero():
    for bad in ("", "x", "0:1", "1:0", "-2:1", None):
        assert parse_scale(bad, 100.0) == 100.0


def test_the_enlargements_are_in_the_list():
    from core.composition import COMMON_SCALES
    shown = [format_scale(n) for n in COMMON_SCALES]
    for s in ("10:1", "5:1", "2:1", "1:1", "1:50", "1:100"):
        assert s in shown


def test_the_title_block_field_says_it_too():
    from core.composition import expand_fields, set_field_context
    c = Composicion()
    c.frames.append(MarcoVista(scale_n=0.1))
    set_field_context(comp=c)
    try:
        assert expand_fields("{escala}") == "10:1"       # not «1:0.1»
        assert expand_fields("ESCALA {escala}") == "ESCALA 10:1"
    finally:
        set_field_context()


# ---- 2. sections are lettered, and can be relettered --------------------

def test_a_new_section_takes_a_LETTER_not_a_number():
    """«Las secciones se nombran así: no suele ser un 1, sino A-A, B-B»
    (50:45). The mark draws the letter at both ends, so «A … A»."""
    from core.section import SectionPlane, next_symbol
    V = QVector3D
    planes = []
    for _ in range(4):
        planes.append(SectionPlane(V(0, 0, 0), V(0, 0, 1),
                                   symbol=next_symbol(planes)))
    assert [p.symbol for p in planes] == ["A", "B", "C", "D"]
    # a gap is filled, and past Z it carries
    assert next_symbol([planes[0], planes[2]]) == "B"
    assert next_symbol([SectionPlane(V(0, 0, 0), V(0, 0, 1), symbol=chr(65 + i))
                        for i in range(26)]) == "AA"


def test_the_section_tool_letters_the_plane_it_places():
    import inspect
    from tools import section
    src = inspect.getsource(section.SectionPlaneTool.on_click)
    assert "next_symbol(planes)" in src
    assert 'symbol=str(count)' not in src


def test_the_plane_can_be_renamed_after_it_is_placed():
    """He could not find where: the prompt only ever appeared the moment a
    plane was placed. It is on the plane's own right-click menu now, right
    under Reverse / Active Cut / Align View."""
    from pathlib import Path
    text = (Path(__file__).resolve().parents[1]
            / "views/main_window.py").read_text()
    i = text.index('menu.addAction(tr("Align View")')
    near = text[i:i + 500]
    assert "Name and symbol" in near
    assert "prompt_section_name" in near


# ---- 3. the N of the north arrow ----------------------------------------

def test_the_north_arrow_keeps_its_box():
    """The letter moved, nothing else: a sheet's north arrow stays put."""
    from core.composition import FlechaNorte
    a = FlechaNorte(size_mm=20.0)
    assert (a.w_mm, a.h_mm) == (20.0, 20.0)
    old = Composicion.from_dict({"nortes": [{"x_mm": 1.0, "size_mm": 20.0}]})
    assert (old.nortes[0].w_mm, old.nortes[0].h_mm) == (20.0, 20.0)


def _north_ink(n, px=8, pad=0):
    """The inked pixels of a north arrow painted alone, as (x, y)."""
    from PySide6.QtGui import QColor, QImage, QPainter
    from views.composer import paint_norte_mm
    side = int((n.size_mm + 2 * pad) * px)
    img = QImage(side, side, QImage.Format_RGB32)
    img.fill(QColor(255, 255, 255))
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing, False)
    p.scale(px, px)
    p.translate(pad, pad)
    paint_norte_mm(p, n)
    p.end()
    return {(x, y) for y in range(img.height()) for x in range(img.width())
            if img.pixelColor(x, y) != QColor(255, 255, 255)}


def test_the_N_is_drawn_clear_of_the_needle():
    """«La N de norte quizás por aquí arriba estaría mejor, porque ahí se
    ve mal» (Rafael, 33:20), and rendered side by side the needle simply
    swallowed it (Marco, 2026-09-19), so there is no option to put it back
    — there is one north arrow and it reads. At 0° the letter sits above
    the compass with clear air between them."""
    from core.composition import FlechaNorte
    sz, px = 20.0, 8
    ink = _north_ink(FlechaNorte(size_mm=sz), px)
    rows = {y for _x, y in ink}
    circle_top = int((0.50 - 0.30 * 0.92) * sz * px)           # the compass
    letter_bottom = int((0.50 - 0.40 + 0.09) * sz * px)        # the N's foot
    assert min(rows) < letter_bottom                 # the letter is up top
    assert not any(letter_bottom + 1 <= y < circle_top - 1 for y in rows)
    assert any(y >= circle_top for y in rows)                  # the compass


def test_the_N_turns_with_the_needle_and_stays_in_the_box():
    """Marco, 2026-09-20: «cuando giro la N de norte debería la N girar
    también». Turned 90° the letter is at the RIGHT of the compass, not
    above it — and at every angle nothing is painted outside the item's
    own box, or the canvas would leave shreds behind it."""
    from core.composition import FlechaNorte
    sz, px, pad = 20.0, 8, 4
    side = sz * px
    ink = _north_ink(FlechaNorte(size_mm=sz, angle_deg=90.0), px)
    letter = {(x, y) for x, y in ink if x > 0.75 * side}     # right of it all
    assert letter and all(abs(y - side / 2) < 0.12 * side for _x, y in letter)
    assert not any(y < 0.15 * side for _x, y in ink)          # nothing on top
    for deg in (0.0, 37.0, 90.0, 135.0, 180.0, 250.0):
        out = _north_ink(FlechaNorte(size_mm=sz, angle_deg=deg), px, pad)
        lo, hi = pad * px, (pad + sz) * px
        assert all(lo <= x < hi and lo <= y < hi for x, y in out), deg
