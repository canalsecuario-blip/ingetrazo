# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""Labels with a leader (LayOut's Label) and double-click text editing."""
from __future__ import annotations

import pytest
from PySide6.QtGui import QImage, QPainter

from core.composition import (AddItemCommand, Composicion, EtiquetaItem,
                              MarcoVista, RemoveItemCommand, TextoItem)


def test_label_model_round_trips_and_paints():
    from views.composer import paint_etiqueta_mm
    c = Composicion()
    et = EtiquetaItem(x_mm=80, y_mm=40, ax_mm=-30, ay_mm=20, text="Muro\ncorrido",
                      anchor_uid="f1", a_world=[1, 2, 3], bg_color="#ffffaa")
    AddItemCommand(c, et).do()
    assert c.etiquetas == [et] and et in c.all_items() and et.anchored
    back = Composicion.from_dict(c.to_dict()).etiquetas[0]
    assert (back.text, back.ax_mm, back.a_world) == ("Muro\ncorrido", -30, [1, 2, 3])
    assert back.h_mm > 6.0
    RemoveItemCommand(c, et).do()
    assert c.etiquetas == []
    for arrow in (True, False):
        et.arrow = arrow
        img = QImage(300, 200, QImage.Format_ARGB32)
        img.fill(0xFFFFFFFF)
        p = QPainter(img)
        p.scale(2, 2)
        p.translate(60, 40)
        paint_etiqueta_mm(p, et)
        p.end()
        # the leader (and its head) reach the pointed-at spot
        tx, ty = int((60 - 30) * 2), int((40 + 20) * 2)
        window = [img.pixel(tx + dx, ty + dy) & 0xFFFFFF
                  for dx in range(-2, 7) for dy in range(-6, 3)]
        assert any(px != 0xFFFFFF for px in window), arrow


def _composer(monkeypatch):
    from views.composer import ComposerWindow
    from views.main_window import MainWindow
    monkeypatch.setattr(ComposerWindow, "render_frame", lambda self, f: None)
    win = MainWindow()
    return win, ComposerWindow(win)


def _close(win, comp):
    comp.close()
    win._saved_version = win.viewport.scene.version
    win.close()


def test_label_tool_places_anchored_and_follows_the_frame(monkeypatch):
    win, comp = _composer(monkeypatch)
    try:
        frame = comp.comp.frames[0]
        frame.uid = ""
        comp.tool_mode = "etiqueta"
        world = (1.0, 2.0, 0.5)
        comp.place_tool(50.0, 60.0, 90.0, 30.0, hit_a=(50.0, 60.0, world, frame))
        et = comp.comp.etiquetas[-1]
        assert (et.x_mm, et.y_mm) == (90.0, 30.0)
        assert (et.ax_mm, et.ay_mm) == (-40.0, 30.0)
        assert et.anchored and et.anchor_uid == frame.uid and et.a_world == [1, 2, 0.5]
        assert comp.tool_mode == "select"                 # only cotas stay armed
        assert comp._item_label(et).startswith("Label")   # "Etiqueta" in es
        # The frame moves 10 mm right: the pointed-at spot follows the model
        # (page point shifts), the text block stays where it was.
        monkeypatch.setattr(comp, "frame_snap_points",
                            lambda f: (None, __import__("numpy").empty((0, 3))))
        pages = {}

        def fake_w2p(f, pts):
            return [(f.x_mm + 30.0, f.y_mm + 20.0) for _ in pts]
        monkeypatch.setattr(comp, "_frame_world_to_page", fake_w2p)
        comp._reproject_anchored_cotas()
        first = (et.ax_mm, et.ay_mm)
        frame.x_mm += 10.0
        comp._reproject_anchored_cotas()
        assert (et.x_mm, et.y_mm) == (90.0, 30.0)
        assert et.ax_mm == pytest.approx(first[0] + 10.0)
        assert et.ay_mm == pytest.approx(first[1])
    finally:
        _close(win, comp)


def test_double_click_edits_text_blocks_and_labels(monkeypatch):
    from views.composer import EtiquetaCanvasItem, TextItem
    win, comp = _composer(monkeypatch)
    try:
        t = TextoItem(x_mm=20, y_mm=20, text="hola")
        et = EtiquetaItem(x_mm=60, y_mm=60, text="Etiqueta")
        comp.comp.texts.append(t)
        comp.comp.etiquetas.append(et)
        comp._rebuild_canvas()
        items = {id(it.model): it for it in comp.canvas.items()
                 if isinstance(it, (TextItem, EtiquetaCanvasItem))}
        from views.composer import InlineTextEditor
        # In-place editor over the text block, same font scale as the paint.
        comp.edit_text_item(items[id(t)])
        ed = comp._inline_editor
        assert isinstance(ed, InlineTextEditor) and ed.toPlainText() == "hola"
        assert ed.scale() == pytest.approx(t.size_pt * 25.4 / 72.0 / 100.0 * 0.75)
        ed.setPlainText("hola mundo\n")
        ed.finish(commit=True)
        assert t.text == "hola mundo" and comp._inline_editor is None
        assert ed.scene() is None
        comp.edit_text_item(items[id(et)])
        ed = comp._inline_editor
        ed.setPlainText("Muro eje A")
        ed.finish(commit=True)
        assert et.text == "Muro eje A"
        comp.history.undo()
        assert et.text == "Etiqueta"
        # Esc cancels, and a second double-click replaces a pending editor.
        comp.edit_text_item(items[id(et)])
        first = comp._inline_editor
        first.setPlainText("basura")
        first.finish(commit=False)
        assert et.text == "Etiqueta" and comp._inline_editor is None
        comp.edit_text_item(items[id(t)])
        comp.edit_text_item(items[id(et)])
        assert comp._inline_editor.item is items[id(et)]
        comp.end_inline_edit(None, None)
        assert comp._inline_editor is None
        assert comp._style_fields_for(et)[0] is EtiquetaItem
        assert "etiqueta" in [m for m, *_ in type(comp).TOOLS]
    finally:
        _close(win, comp)


def test_the_leader_leaves_the_text_not_the_far_edge_of_a_wide_block():
    """Marco, 2026-09-08: «¿por qué no me sale la línea hasta el texto?» —
    a 50 mm block around two short words started its leader at the block's
    bottom middle, 15 mm past the words. It starts at the text now."""
    from PySide6.QtGui import QImage, QPainter
    from core.composition import EtiquetaItem
    from views.composer import (_label_block_h, etiqueta_ink_w_mm,
                                etiqueta_leader_start, paint_etiqueta_mm)
    et = EtiquetaItem(text="ab", w_mm=50.0, ax_mm=40.0, ay_mm=5.0,
                      size_pt=11.0, arrow=False, bg_color="")
    tw = etiqueta_ink_w_mm(et)
    assert 3.0 < tw < 12.0                             # the two letters
    sx, sy = etiqueta_leader_start(et)
    assert abs(sx - (tw + 0.8)) < 1e-9                 # right edge of the text
    assert abs(sy - _label_block_h(et) / 2) < 1e-9     # mid-height of the INK
    img = QImage(600, 200, QImage.Format_RGB32)
    img.fill(0xFFFFFFFF)
    p = QPainter(img)
    p.scale(8.0, 8.0)
    p.translate(5.0, 5.0)
    paint_etiqueta_mm(p, et)
    p.end()
    # midway between the text and the point the leader is a hair above
    # y = 5 mm; the old block-bottom start would have put it ~4 mm lower
    mx = (sx + 40.0) / 2
    my = sy + (5.0 - sy) * (mx - sx) / (40.0 - sx)
    px, py = round((5.0 + mx) * 8), round((5.0 + my) * 8)
    assert any((img.pixel(px, y) & 0xFF) < 160 for y in range(py - 3, py + 4))
    assert not any((img.pixel(px, y) & 0xFF) < 160
                   for y in range(py + 20, py + 45))


def test_the_background_hugs_the_text_not_the_wrap_box():
    """Marco, 2026-09-14: «BUZÓN» on the plaza sheet sat in a 50 mm white
    slab that blanked the drawing beside it. The background (and the
    clickable area) now cover the inked text plus the pad; ``w_mm`` stays
    the wrap width."""
    from PySide6.QtGui import QImage, QPainter
    from core.composition import EtiquetaItem
    from views.composer import (TEXT_BG_PAD_MM, etiqueta_bg_rect_mm,
                                etiqueta_ink_w_mm, paint_etiqueta_mm)
    et = EtiquetaItem(text="BUZÓN", w_mm=50.0, ax_mm=-20.0, ay_mm=15.0,
                      size_pt=11.0, arrow=False, bg_color="#ffffff")
    tw = etiqueta_ink_w_mm(et)
    r = etiqueta_bg_rect_mm(et)
    assert 8.0 < tw < 20.0
    assert r.width() == pytest.approx(tw + 2 * TEXT_BG_PAD_MM)
    assert r.width() < 30.0 < et.w_mm                 # far narrower than the box
    # Paint over a grey page: beside the word the page must stay grey.
    img = QImage(600, 200, QImage.Format_RGB32)
    img.fill(0xFF808080)
    p = QPainter(img)
    p.scale(8.0, 8.0)
    p.translate(5.0, 5.0)
    paint_etiqueta_mm(p, et)
    p.end()
    # a point in the pad just past the last glyph: slab, no ink
    inside = img.pixelColor(round((5.0 + tw + TEXT_BG_PAD_MM * 0.5) * 8),
                            round((5.0 + et.h_mm * 0.5) * 8))
    beside = img.pixelColor(round((5.0 + 40.0) * 8), round((5.0 + 2.0) * 8))
    assert inside.red() == 255                         # white slab under the text
    assert beside.red() == 128                         # the page shows through


def test_the_corner_handle_resizes_the_wrap_box(monkeypatch):
    """The dashed selection box of a label showed a resize handle that did
    nothing (Marco, 2026-09-14: «me gustaría poder redimensionarlo»).
    Dragging it now sets the wrap width — one undo step — and never
    touches the pointed-at spot."""
    from types import SimpleNamespace
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtWidgets import QGraphicsSceneMouseEvent
    from core.composition import EtiquetaItem
    from views.composer import EtiquetaCanvasItem, _HANDLE_MM

    et = EtiquetaItem(text="BUZÓN", w_mm=50.0, ax_mm=-20.0, ay_mm=15.0,
                      x_mm=100.0, y_mm=60.0)
    pushed = []
    composer = SimpleNamespace(
        push_geometry_edit=lambda m, cur, before: pushed.append((cur, before)),
        on_item_geometry=lambda item, final=False: None,
        note_drag_start=lambda: None, snap_targets_x=lambda *a: [],
        snap_targets_y=lambda *a: [], canvas=None,
        on_selection_changed=lambda *a: None)
    item = EtiquetaCanvasItem(composer, et)
    assert item._on_resize_handle(QPointF(et.w_mm, et.h_mm))
    assert not item._on_resize_handle(QPointF(et.w_mm / 2, et.h_mm / 2))

    def ev(kind, x, y):
        e = QGraphicsSceneMouseEvent(kind)
        e.setPos(QPointF(x, y))
        e.setButton(Qt.LeftButton)
        e.setButtons(Qt.LeftButton)
        return e

    item.mousePressEvent(ev(QGraphicsSceneMouseEvent.GraphicsSceneMousePress,
                            et.w_mm, et.h_mm))
    assert item._resizing
    item.mouseMoveEvent(ev(QGraphicsSceneMouseEvent.GraphicsSceneMouseMove, 18.0, 30.0))
    assert et.w_mm == pytest.approx(18.0)
    assert (et.ax_mm, et.ay_mm) == (-20.0, 15.0)        # the spot stays
    item.mouseMoveEvent(ev(QGraphicsSceneMouseEvent.GraphicsSceneMouseMove, 1.0, 30.0))
    assert et.w_mm == EtiquetaCanvasItem.MIN_W_MM       # never collapses
    item.mouseReleaseEvent(ev(QGraphicsSceneMouseEvent.GraphicsSceneMouseRelease, 1.0, 30.0))
    assert not item._resizing
    assert pushed and pushed[-1][0]["w_mm"] == EtiquetaCanvasItem.MIN_W_MM
    assert pushed[-1][1]["w_mm"] == 50.0


def test_the_inline_editor_sits_exactly_on_the_painted_text():
    """Double-click showed the words shifted and re-wrapped over the
    painted label («se distorsiona», Marco 2026-09-14): the editor's
    document margin pushed them 4 units right/down and ate wrap width.
    No margin now, and the wrap width is the label's own."""
    from types import SimpleNamespace
    from core.composition import EtiquetaItem
    from views.composer import EtiquetaCanvasItem, InlineTextEditor, PT_TO_MM

    et = EtiquetaItem(text="Rampa de acceso", w_mm=30.0, size_pt=11.0)
    composer = SimpleNamespace(on_selection_changed=lambda *a: None)
    item = EtiquetaCanvasItem(composer, et)
    ed = InlineTextEditor(composer, item)
    assert ed.document().documentMargin() == 0.0
    s = et.size_pt * PT_TO_MM / 100.0 * 0.75
    assert ed.textWidth() * s == pytest.approx(30.0)
    assert ed.pos() == item.pos()


def _stub_composer(pushed):
    from types import SimpleNamespace
    return SimpleNamespace(
        push_geometry_edit=lambda m, cur, before: pushed.append((cur, before)),
        on_item_geometry=lambda item, final=False: None,
        note_drag_start=lambda: None, snap_targets_x=lambda *a: [],
        snap_targets_y=lambda *a: [], canvas=None,
        on_selection_changed=lambda *a: None)


def _mouse(kind, x, y, ctrl=False):
    from PySide6.QtCore import QPointF, Qt
    from PySide6.QtWidgets import QGraphicsSceneMouseEvent
    e = QGraphicsSceneMouseEvent(kind)
    e.setPos(QPointF(x, y))
    e.setButton(Qt.LeftButton)
    e.setButtons(Qt.LeftButton)
    e.setModifiers(Qt.ControlModifier if ctrl else Qt.NoModifier)
    return e


def test_one_label_can_point_at_several_things():
    """Marco, 2026-09-14: «¿qué pasa si quiero señalar 2 o 3 cosas con la
    misma etiqueta?» — a multileader. Extra leaders live in ``leaders``,
    paint one arrow each, ride along when the words move, round-trip, and
    Ctrl-dragging an arrow tip pulls a new one off it; dropping an extra
    tip on the words removes it. One undo step per gesture."""
    from PySide6.QtCore import QPointF
    from PySide6.QtWidgets import QGraphicsSceneMouseEvent as E
    from core.composition import Composicion, EtiquetaItem
    from views.composer import EtiquetaCanvasItem, etiqueta_leader_start

    et = EtiquetaItem(text="BUZÓN", w_mm=30.0, ax_mm=-20.0, ay_mm=15.0,
                      x_mm=100.0, y_mm=60.0)
    et.add_leader(40.0, 20.0, anchor_uid="f1", a_world=[1.0, 2.0, 0.0])
    assert et.spots() == [(-20.0, 15.0), (40.0, 20.0)]
    # each leader leaves the text on the edge facing its spot
    assert etiqueta_leader_start(et)[0] == pytest.approx(-0.8)
    assert etiqueta_leader_start(et, (40.0, 20.0))[0] > 5.0
    # the document round trip keeps the extra leaders
    comp = Composicion()
    comp.etiquetas = [et]
    again = Composicion.from_dict(comp.to_dict())
    assert again.etiquetas[0].leaders == [{"ax_mm": 40.0, "ay_mm": 20.0,
                                          "anchor_uid": "f1",
                                          "a_world": [1.0, 2.0, 0.0]}]

    pushed = []
    item = EtiquetaCanvasItem(_stub_composer(pushed), et)
    assert item._spot_at(QPointF(40.0, 20.0)) == 1
    assert item._spot_at(QPointF(-20.0, 15.0)) == 0
    assert item.boundingRect().right() > 40.0

    # Ctrl-drag the extra tip: a third leader is born and dragged away.
    item.mousePressEvent(_mouse(E.GraphicsSceneMousePress, 40.0, 20.0, ctrl=True))
    assert len(et.leaders) == 2 and item._drag_spot == 2
    item.mouseMoveEvent(_mouse(E.GraphicsSceneMouseMove, 55.0, -10.0))
    assert et.spots()[2] == (55.0, -10.0)
    assert et.spots()[1] == (40.0, 20.0)                # the source stays
    item.mouseReleaseEvent(_mouse(E.GraphicsSceneMouseRelease, 55.0, -10.0))
    assert len(pushed) == 1 and len(pushed[-1][0]["leaders"]) == 2
    assert len(pushed[-1][1]["leaders"]) == 1           # undo = before

    # Drag the first extra tip by hand: it comes off the model.
    item.mousePressEvent(_mouse(E.GraphicsSceneMousePress, 40.0, 20.0))
    item.mouseMoveEvent(_mouse(E.GraphicsSceneMouseMove, 42.0, 22.0))
    item.mouseReleaseEvent(_mouse(E.GraphicsSceneMouseRelease, 42.0, 22.0))
    assert et.leaders[0]["anchor_uid"] == "" and et.leaders[0]["a_world"] is None

    # Drop an extra tip on the words: gone.
    item.mousePressEvent(_mouse(E.GraphicsSceneMousePress, 55.0, -10.0))
    item.mouseMoveEvent(_mouse(E.GraphicsSceneMouseMove, 3.0, 3.0))
    item.mouseReleaseEvent(_mouse(E.GraphicsSceneMouseRelease, 3.0, 3.0))
    assert len(et.leaders) == 1
    assert len(pushed[-1][0]["leaders"]) == 1 and len(pushed[-1][1]["leaders"]) == 2


def test_the_label_tool_adds_a_leader_when_the_second_click_lands_on_a_label(monkeypatch):
    """Label tool: point, then click ON an existing label → that label
    gains an arrow to the point (anchored when the point snapped to model
    geometry), instead of a new label being born. One undo step."""
    win, comp = _composer(monkeypatch)
    try:
        frame = comp.comp.frames[0]
        frame.uid = "f-uid"
        comp.tool_mode = "etiqueta"
        comp.place_tool(50.0, 60.0, 90.0, 30.0)           # a free label
        et = comp.comp.etiquetas[-1]
        assert et.leaders == []
        n = len(comp.comp.etiquetas)
        comp.tool_mode = "etiqueta"
        world = [12.0, 7.0, 0.0]
        # second click inside the label's words (x within its inked width)
        comp.place_tool(20.0, 80.0, 92.0, 33.0, hit_a=(20.0, 80.0, world, frame))
        assert len(comp.comp.etiquetas) == n                 # no new label
        assert et.leaders == [{"ax_mm": 20.0 - 90.0, "ay_mm": 80.0 - 30.0,
                               "anchor_uid": "f-uid", "a_world": world}]
        comp.history.undo()
        assert et.leaders == []
        comp.history.redo()
        assert len(et.leaders) == 1
    finally:
        _close(win, comp)


def _margins_mm(text, w_mm=30.0, size_pt=11.0):
    """Paper between the background slab and the ink, ``(top, bottom)`` in
    mm, measured on a painted label (the leader sent off-picture)."""
    import numpy as np
    from PySide6.QtGui import QImage, QPainter
    from core.composition import EtiquetaItem
    from views.composer import paint_etiqueta_mm
    K = 20
    et = EtiquetaItem(text=text, w_mm=w_mm, size_pt=size_pt, bg_color="#ff0000",
                      arrow=False, ax_mm=200.0, ay_mm=2.0)
    img = QImage(60 * K, 40 * K, QImage.Format_RGB32)
    img.fill(0xFFFFFFFF)
    p = QPainter(img)
    p.setRenderHint(QPainter.Antialiasing)
    p.scale(K, K)
    p.translate(5, 10)
    paint_etiqueta_mm(p, et)
    p.end()
    b = np.frombuffer(img.constBits(), np.uint8).reshape(img.height(), img.bytesPerLine())
    b = b[:, :img.width() * 4].reshape(img.height(), img.width(), 4)
    red = (b[..., 2] > 200) & (b[..., 1] < 80) & (b[..., 0] < 80)
    ink = (b[..., 0] < 110) & (b[..., 1] < 110) & (b[..., 2] < 110)
    rx = np.where(red.any(0))[0]
    ink = ink[:, rx[0]:rx[-1] + 1]
    ry = np.where(red.any(1))[0]
    iy = np.where(ink.any(1))[0]
    return (iy[0] - ry[0]) / K, (ry[-1] - iy[-1]) / K


def test_the_background_hugs_the_letters_top_and_bottom():
    """Marco, 2026-09-14: the white background sat on a blank band under
    the last line and another over the first. It now follows the glyphs:
    a hair of paper above accents and below descenders, on one line or
    four, wrapped or typed — never ink outside the slab, never a band."""
    cases = ["Luminaria eléctrica", "BUZÓN", "Rampa de\nacceso",
             "Escultura de\ncampesino con\npedestal",
             "gyp\nqjg\npedestal\nabc",
             "Luminaria eléctrica en poste de concreto"]   # wraps to 3
    for text in cases:
        top, bottom = _margins_mm(text)
        assert 0.2 <= top <= 1.6, (text, top)      # lowercase-only tops sit lower
        assert 0.2 <= bottom <= 1.2, (text, bottom)


def test_the_leader_starts_with_a_dot_at_the_words():
    """Marco, 2026-09-14: «el inicio de la línea donde está el texto
    debería ser un punto». A filled dot sits where each leader leaves the
    words; ``dot=False`` turns it off (and old documents default to on)."""
    from PySide6.QtGui import QImage, QPainter
    from core.composition import Composicion, EtiquetaItem
    from views.composer import etiqueta_leader_start, paint_etiqueta_mm

    def ink_at_start(dot: bool) -> int:
        et = EtiquetaItem(text="BUZÓN", w_mm=30.0, ax_mm=40.0, ay_mm=2.0,
                          arrow=False, bg_color="", dot=dot, stroke_mm=0.25)
        sx, sy = etiqueta_leader_start(et)
        K = 20
        img = QImage(60 * K, 20 * K, QImage.Format_RGB32)
        img.fill(0xFFFFFFFF)
        p = QPainter(img)
        p.setRenderHint(QPainter.Antialiasing)
        p.scale(K, K)
        p.translate(5, 5)
        paint_etiqueta_mm(p, et)
        p.end()
        # count dark pixels in a 1.2 mm box around the start: the dot fills
        # it, the bare 0.25 mm line barely touches it
        n = 0
        for dy in range(-12, 13):
            for dx in range(-12, 13):
                c = img.pixelColor(round((5 + sx) * K) + dx, round((5 + sy) * K) + dy)
                n += c.red() < 128
        return n

    assert ink_at_start(True) > 3 * ink_at_start(False)
    assert Composicion.from_dict({"etiquetas": [{"text": "x"}]}).etiquetas[0].dot is True
