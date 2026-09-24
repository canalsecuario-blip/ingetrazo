"""Help ▸ About: the contributors roll up like film credits (Marco, 23-09)."""
from __future__ import annotations

from PySide6.QtWidgets import QApplication

from views.about_dialog import CONTRIBUTORS, AboutDialog, _credits_html

_app = QApplication.instance() or QApplication([])


def test_everyone_is_in_the_credits():
    html = _credits_html(CONTRIBUTORS)
    for who in ("Pedro Caeiro", "Rafael García Rodríguez", "Ahsan Mehmood",
                "dafrobozao", "Félix Riestra", "Sherod Taylor"):
        assert who in html


def test_the_credits_roll_by_themselves_and_loop():
    dlg = AboutDialog(None, "0.0.0")
    dlg.resize(520, 600)
    dlg.show()
    _app.processEvents()
    roll = dlg.credits
    assert roll.running                       # nothing to click
    assert roll.span > roll.height()          # more names than the band shows
    start = roll.offset
    roll.tick()
    assert roll.offset != start               # it moves
    for _ in range(roll.span + 5):
        roll.tick()
    assert 0 <= roll.offset < roll.span       # and comes round again
    dlg.close()
