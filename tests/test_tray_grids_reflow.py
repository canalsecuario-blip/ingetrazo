# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""The tray's material swatches and component buttons reflow with the
width: a widened tray shows more per row instead of a blank right half
(Marco, 2026-09-15)."""
from __future__ import annotations

import pytest
from PySide6.QtWidgets import QApplication, QToolButton, QWidget

from views.tray import FlowLayout


@pytest.fixture(scope="module")
def app():
    a = QApplication.instance()
    if a is None:
        a = QApplication([])
    elif not isinstance(a, QApplication):
        pytest.skip("another Qt application flavour is already running")
    return a


def _swatches(n, px=44, spacing=2):
    host = QWidget()
    flow = FlowLayout(host, spacing=spacing)
    for _ in range(n):
        b = QToolButton()
        b.setFixedSize(px, px)
        flow.addWidget(b, 0, 0)          # the old grid call shape still works
    return host, flow


def test_more_columns_fit_when_the_tray_widens(app):
    host, flow = _swatches(12)
    assert flow.count() == 12
    assert flow.columns_at(240) == 5      # the narrow tray: five per row
    assert flow.columns_at(470) == 10     # widened: ten per row
    assert flow.columns_at(1000) == 12
    # And the block gets shorter as it gets wider.
    assert flow.heightForWidth(240) > flow.heightForWidth(470) > flow.heightForWidth(1000)
    assert flow.hasHeightForWidth()


def test_the_items_are_laid_out_row_by_row(app):
    host, flow = _swatches(7)
    host.resize(240, 200)
    host.show()
    app.processEvents()
    pos = [(flow.itemAt(i).widget().x(), flow.itemAt(i).widget().y()) for i in range(7)]
    assert len({y for _x, y in pos}) == 2                 # two rows
    first_row = [x for x, y in pos if y == pos[0][1]]
    assert first_row == sorted(first_row) and len(first_row) == 5
    host.hide()


def test_take_at_empties_the_flow(app):
    host, flow = _swatches(3)
    while flow.count():
        flow.takeAt(0)
    assert flow.count() == 0 and flow.itemAt(0) is None
