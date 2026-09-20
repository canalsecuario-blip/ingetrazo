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

def test_the_N_sits_above_the_compass_by_default():
    """«La N de norte quizás por aquí arriba estaría mejor, porque ahí se
    ve mal» (33:20) — it was drawn over the black-and-white needle."""
    from core.composition import FlechaNorte
    assert FlechaNorte().label_pos == "top"
    old = Composicion.from_dict({"nortes": [{"x_mm": 1.0, "size_mm": 20.0}]})
    assert old.nortes[0].label_pos == "top"


def test_the_north_arrow_keeps_its_box_either_way():
    from core.composition import FlechaNorte
    a, b = FlechaNorte(size_mm=20.0), FlechaNorte(size_mm=20.0,
                                                  label_pos="centre")
    assert (a.w_mm, a.h_mm) == (b.w_mm, b.h_mm) == (20.0, 20.0)


def test_the_N_really_moves_up_the_page():
    """Painted: with the N on top, the letter's ink is in the upper band
    and the compass circle is not."""
    from PySide6.QtGui import QColor, QImage, QPainter
    from core.composition import FlechaNorte
    from views.composer import paint_norte_mm

    def ink_rows(n):
        px = 8
        img = QImage(int(n.size_mm * px), int(n.size_mm * px),
                     QImage.Format_RGB32)
        img.fill(QColor(255, 255, 255))
        p = QPainter(img)
        p.setRenderHint(QPainter.Antialiasing, False)
        p.scale(px, px)
        paint_norte_mm(p, n)
        p.end()
        return {y for y in range(img.height())
                for x in range(img.width())
                if img.pixelColor(x, y) != QColor(255, 255, 255)}

    sz, px = 20.0, 8
    top = ink_rows(FlechaNorte(size_mm=sz))
    # with the N on top the compass starts well down the box, and the only
    # ink above it is the letter
    circle_top = int((0.60 - 0.38 * 0.92) * sz * px)          # ≈ row 40
    assert min(top) < circle_top - px                          # the N, clear
    centre = ink_rows(FlechaNorte(size_mm=sz, label_pos="centre"))
    # the old look has nothing above the circle at all: its topmost ink IS
    # the circle, and the letter sits down on the needle
    old_circle_top = int(0.5 * (1.0 - 0.92) * sz * px)         # ≈ row 6
    assert min(centre) <= old_circle_top + px


# ---- 4. an image magnetises to the drawing under it ---------------------

def test_only_an_image_snaps_to_the_model_geometry():
    from views.composer import (CotaCanvasItem, FrameItem, ImageItem,
                                TextItem)
    assert ImageItem.SNAPS_TO_DRAWING is True
    for other in (FrameItem, TextItem, CotaCanvasItem):
        assert other.SNAPS_TO_DRAWING is False


def test_a_dragged_image_lands_its_nearest_corner_on_a_drawn_point(
        monkeypatch):
    from views.composer import ComposerWindow, ImageItem
    from views.main_window import MainWindow
    from core.composition import ImagenItem
    monkeypatch.setattr(ComposerWindow, "render_frame", lambda self, f: None)
    win = MainWindow()
    comp = None
    try:
        comp = ComposerWindow(win)
        comp.comp.images.append(ImagenItem(x_mm=50.0, y_mm=50.0,
                                           w_mm=40.0, h_mm=30.0))
        comp._rebuild_canvas()
        item = next(it for it in comp.canvas.items()
                    if isinstance(it, ImageItem))
        # one drawn point, 1 mm off the image's bottom-right corner
        target = (91.0, 81.0)
        monkeypatch.setattr(
            ComposerWindow, "nearest_snap_point",
            lambda self, x, y, thr: (target + ((0.0, 0.0, 0.0), None)
                                     if abs(x - target[0]) <= thr
                                     and abs(y - target[1]) <= thr else None))
        got = item._snap_corner_to_drawing(50.0, 50.0, 40.0, 30.0)
        assert got == pytest.approx((51.0, 51.0))   # the corner lands on it
        # …and a corner nowhere near a drawn point is left alone
        assert item._snap_corner_to_drawing(5.0, 5.0, 40.0, 30.0) is None
    finally:
        if comp is not None:
            comp.close()
        win._saved_version = win.viewport.scene.version
        win.close()


# ---- 5. a new view wearing a dead one's render --------------------------

def test_a_deleted_frames_caches_are_forgotten(monkeypatch):
    """«Pongo una ventana y me muestra ese previo que yo ya no tengo»
    (33:40). The caches are keyed on id(frame), and CPython hands the same
    address to the next object of that size — so the new frame inherited
    the dead one's render, lines, fills, snap points and annotations."""
    from views.composer import ComposerWindow
    from views.main_window import MainWindow
    monkeypatch.setattr(ComposerWindow, "render_frame", lambda self, f: None)
    win = MainWindow()
    comp = None
    try:
        comp = ComposerWindow(win)
        doomed = comp.comp.frames[0]
        fid = id(doomed)
        comp.render_cache[fid] = "a render nobody should see again"
        comp.hlr_cache[fid] = "lines"
        comp.annot_cache[fid] = ["annots"]
        comp._stale.add(fid)

        comp.comp.frames.remove(doomed)          # as a delete leaves it
        comp._rebuild_canvas()

        assert fid not in comp.render_cache
        assert fid not in comp.hlr_cache
        assert fid not in comp.annot_cache
        assert fid not in comp._stale
    finally:
        if comp is not None:
            comp.close()
        win._saved_version = win.viewport.scene.version
        win.close()


def test_the_sweep_spares_the_frames_of_the_other_sheets(monkeypatch):
    """Switching sheets must not throw away renders that cost seconds."""
    from views.composer import ComposerWindow
    from views.main_window import MainWindow
    monkeypatch.setattr(ComposerWindow, "render_frame", lambda self, f: None)
    win = MainWindow()
    comp = None
    try:
        comp = ComposerWindow(win)
        other = Composicion(name="Lámina 2")
        other.frames.append(MarcoVista())
        win.viewport.scene.compositions.append(other)
        keep = id(other.frames[0])
        comp.render_cache[keep] = "the other sheet's render"
        comp._rebuild_canvas()
        assert keep in comp.render_cache
    finally:
        if comp is not None:
            comp.close()
        win._saved_version = win.viewport.scene.version
        win.close()
