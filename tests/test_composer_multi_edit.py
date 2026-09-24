"""A property changed in the panel goes to every selected item of that kind
(Marco, 24-09: several cotas selected, the unit set from cm to m — «solo una
nomás cambia, las demás no»). Only the changed field travels; one undo
step puts them all back."""
from __future__ import annotations

from core.composition import AddItemCommand, CotaItem


def test_the_unit_reaches_every_selected_cota_in_one_undo_step(monkeypatch):
    from views.composer import ComposerWindow
    from views.main_window import MainWindow
    monkeypatch.setattr(ComposerWindow, "render_frame", lambda self, f: None)
    win = MainWindow()
    comp = ComposerWindow(win)
    try:
        cotas = [CotaItem(x_mm=30.0, y_mm=30.0 + 20 * i, dx_mm=40.0,
                          units="cm", text_mm=3.0 + i) for i in range(3)]
        for c in cotas:
            comp.history.execute(AddItemCommand(comp.comp, c))
        comp._rebuild_canvas()
        for c in cotas:
            comp._item_for(c).setSelected(True)
        comp.on_selection_changed()          # the panel shows the first one
        comp.cota_units.setCurrentText("m")
        assert [c.units for c in cotas] == ["m", "m", "m"]
        assert [c.text_mm for c in cotas] == [3.0, 4.0, 5.0]   # untouched
        comp.history.undo()
        assert [c.units for c in cotas] == ["cm", "cm", "cm"]
    finally:
        comp.close()
        win._saved_version = win.viewport.scene.version
        win.close()


def _sheet(monkeypatch, n=3):
    from views.composer import ComposerWindow
    from views.main_window import MainWindow
    monkeypatch.setattr(ComposerWindow, "render_frame", lambda self, f: None)
    win = MainWindow()
    comp = ComposerWindow(win)
    cotas = [CotaItem(x_mm=30.0, y_mm=40.0 + 30 * i, dx_mm=60.0,
                      sep_mm=6.0 + 4 * i, units="cm") for i in range(n)]
    for c in cotas:
        comp.history.execute(AddItemCommand(comp.comp, c))
    comp._rebuild_canvas()
    return win, comp, cotas


def _done(win, comp):
    comp.close()
    win._saved_version = win.viewport.scene.version
    win.close()


def test_the_edit_lands_on_the_cota_the_panel_shows(monkeypatch):
    """Qt lists the selection in no set order: filled from one cota, the
    panel's edit went to another, which took the first one's offset and
    jumped (Marco, 24-09: «algunas cotas cambian de ubicación»)."""
    win, comp, cotas = _sheet(monkeypatch)
    try:
        items = [comp._item_for(c) for c in cotas]
        items[0].setSelected(True)
        comp.on_selection_changed()                # the panel shows cota 0
        for it in items[1:]:
            it.setSelected(True)
        monkeypatch.setattr(comp.canvas, "selectedItems",
                            lambda: list(reversed(items)))
        comp.on_selection_changed()
        comp.cota_units.setCurrentText("m")
        assert [c.units for c in cotas] == ["m", "m", "m"]
        assert [c.sep_mm for c in cotas] == [6.0, 10.0, 14.0]   # none moved
    finally:
        _done(win, comp)


def test_ctrl_click_on_the_text_adds_and_removes_a_cota(monkeypatch):
    from PySide6.QtCore import QPoint, Qt
    from PySide6.QtTest import QTest
    from views.composer import cota_label_anchor
    win, comp, cotas = _sheet(monkeypatch)
    try:
        comp.show()
        view = comp._view

        def ctrl_click_text(c, wobble=0):
            item = comp._item_for(c)
            lx, ly = cota_label_anchor(c)
            p = view.mapFromScene(item.mapToScene(lx, ly))
            QTest.mousePress(view.viewport(), Qt.LeftButton,
                             Qt.ControlModifier, p)
            QTest.mouseRelease(view.viewport(), Qt.LeftButton,
                               Qt.ControlModifier, p + QPoint(wobble, 0))

        for c in cotas:
            ctrl_click_text(c)
        assert all(comp._item_for(c).isSelected() for c in cotas)
        ctrl_click_text(cotas[1], wobble=1)          # a shaky hand
        assert all(c.text_dx_mm == 0.0 for c in cotas)     # no text dragged
        assert [comp._item_for(c).isSelected() for c in cotas] == [
            True, False, True]
    finally:
        _done(win, comp)
