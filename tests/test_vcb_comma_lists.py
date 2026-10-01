# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""#152: the Rectangle's VCB takes "200,100" as two values, the usual convention,
while a comma stays the decimal separator everywhere a single value makes
sense ("2,5" is 2.5) and whenever ";" or a space already separates fields."""
from __future__ import annotations

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QVector3D
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

_app = QApplication.instance() or QApplication([])

from views.viewport import Viewport  # noqa: E402


def _parse(text, lists=False):
    return Viewport._parse_value_buffer(text, comma_lists=lists)


def test_a_multi_value_tool_reads_the_comma_as_a_list_separator():
    assert _parse("200,100", lists=True) == pytest.approx((200.0, 100.0))
    assert _parse("3,2,1", lists=True) == pytest.approx((3.0, 2.0, 1.0))
    # with ";" or a space already there, the comma is the decimal again
    assert _parse("2,5;1,2", lists=True) == pytest.approx((2.5, 1.2))
    assert _parse("200, 100", lists=True) == pytest.approx((200.0, 100.0))
    assert _parse("200;100", lists=True) == pytest.approx((200.0, 100.0))


def test_everywhere_else_the_comma_is_still_the_decimal():
    assert _parse("2,5") == pytest.approx(2.5)
    assert _parse("200,100") == pytest.approx(200.1)       # as before
    assert _parse("2,5;1,2") == pytest.approx((2.5, 1.2))
    assert _parse("200 100") == pytest.approx((200.0, 100.0))
    assert _parse("200, 100") == pytest.approx((200.0, 100.0))


def test_typing_200_comma_100_in_the_rectangle_draws_200_by_100():
    from views.main_window import MainWindow

    win = MainWindow()
    try:
        vp = win.viewport
        win._activate_tool("rectangle")
        tool = vp.active_tool
        assert getattr(tool, "vcb_comma_lists", False)
        tool.start_point = QVector3D(0, 0, 0)
        tool.hover_point = QVector3D(1, 1, 0)          # dragging toward +x +y
        got = []
        real = tool.on_value
        tool.on_value = lambda v, value: (got.append(value), real(v, value))[1]
        vp.setFocus()
        QTest.keyClicks(vp, "200,100")
        QTest.keyClick(vp, Qt.Key_Return)
        assert got, "Enter did not reach the tool"
        assert got[-1] == pytest.approx((200.0, 100.0))
    finally:
        win._saved_version = win.viewport.scene.version
        win.close()
