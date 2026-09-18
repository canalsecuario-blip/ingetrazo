# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""Every status hint fits the bar, in both languages.

The bar caps its message at half its width (Marco, 2026-09-15: «que no
llegue hasta el otro extremo derecho»), and what does not fit is elided
with an ellipsis — so an overlong line does not wrap, it silently loses its
end. That is where the modifiers live, which is exactly the part you need.

He caught one: «no sale completo el texto». The survey that followed found
it was not one line but SIXTEEN, across eight tools whose hints had grown
over time — and that Spanish is the language that hurts, running a fifth
longer than the English it is translated from.

TWO THINGS THE FIRST VERSION OF THIS TEST GOT WRONG, both found by CI:

1. **It measured in pixels, which are a property of the machine.** The same
   Spanish strings that came to 626/647/650 px here measured 682/704/723 px
   on the GitHub runner. Shaving a margin off the budget does not fix that,
   and CI said so a second time: the margin lands on BOTH machines, so the
   wide one pays for its width twice and fails strings that fit it fine.
   What travels is a character count, calibrated against the widest font we
   have measured; the pixel check stays as the local truth beside it.

2. **It invented phases no tool can be in.** It set ``start_point`` on
   every tool, including the ones that never have one — the section tool
   has no such attribute, so it can never be mid-operation and can never
   carry the Alt clause. Nine characters were nearly cut off a hint to
   satisfy a state that does not exist. It now only starts the tools that
   really do start.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest
from PySide6.QtGui import QFontMetrics, QVector3D
from PySide6.QtWidgets import QApplication

from core.i18n import set_language
from views.status_hints import HINTS, hint_for

_app = QApplication.instance() or QApplication([])

#: The narrowest window we design for — a 1366×768 laptop, which is what
#: sent the toolbar icons back to 24 px in the first place.
_NARROW_PX = 1366

#: THE portable rule, and the reason there is one. Pixels are a property
#: of the machine: the same Spanish hints measure ~5.3 px/character here
#: and up to 5.80 on the GitHub runner, so a hint that fits on the desktop
#: can be cut off in CI or on a user's screen.
#:
#: The obvious patch — measure in pixels and shave a margin off the budget
#: — does not work, and CI said so: the margin gets applied on BOTH
#: machines, so the wide one is charged for its width twice and fails
#: strings that comfortably fit it. A budget that travels has to be
#: counted in something that does not change between machines.
#:
#: 112 characters is the 675 px cap at the worst density we have actually
#: measured anywhere (5.80 px/character, from the runner's own failure
#: output on 2026-09-17), with a little left over.
_MAX_CHARS = 112

#: Every state Alt can be in. The third one, «parallel / perpendicular», is
#: the longest and the first version of this test never measured it.
_MODES = ("all", "off", "parallel_perp")


#: What puts a tool past its idle phase, for the ones whose phase is not
#: the plain ``start_point`` that :func:`views.status_hints.phase_of`
#: checks first.
_STARTERS = {"fillet": ("sizing", True)}


def _start(key: str, tool) -> bool:
    """Put the tool mid-operation. False when it has no such phase."""
    attr, value = _STARTERS.get(key, ("start_point", QVector3D(1.0, 1.0, 0.0)))
    if not hasattr(tool, attr):
        return False
    try:
        setattr(tool, attr, value)
    except AttributeError:      # a read-only property: not ours to drive
        return False
    return True


def _overlong(language: str):
    """Every (tool, phase, mode) hint that would be elided, measured."""
    from views.main_window import MainWindow

    set_language(language)
    win = MainWindow()
    win.show()
    win.resize(_NARROW_PX, 900)
    _app.processEvents()
    vp, bar = win.viewport, win.statusBar()
    fm = QFontMetrics(bar._msg.font())
    # The pixel check is the local truth — does it fit on THIS screen —
    # and the character cap is what makes the guard mean the same thing
    # everywhere. Neither is a margin on the other.
    cap = int(bar.width() * bar.MESSAGE_SHARE) - 4
    bad = []
    try:
        for key in sorted(HINTS):
            try:
                win._activate_tool(key)
            except Exception:       # noqa: BLE001 — not every key is a tool
                continue
            tool = vp.active_tool
            if tool is None:
                continue
            for started in (False, True):
                # Only the tools that really can be mid-operation get
                # driven there, through whatever phase_of reads for them —
                # the fillet goes by ``sizing`` and its ``start_point`` is
                # read-only. Inventing the state on the others would
                # measure a line nobody can ever see.
                if started and not _start(key, tool):
                    continue
                for mode in _MODES:
                    text = hint_for(win._tool_key(tool), tool, None, mode)
                    width = fm.horizontalAdvance(text)
                    if width > cap:
                        bad.append(f"{key} ({width}px > {cap}px): {text}")
                    elif len(text) > _MAX_CHARS:
                        bad.append(f"{key} ({len(text)} chars > {_MAX_CHARS}): {text}")
    finally:
        win._saved_version = vp.scene.version
        win.close()
        set_language("en")
    return bad


@pytest.mark.parametrize("language", ["en", "es"])
def test_no_hint_is_elided_on_a_1366_screen(language):
    bad = _overlong(language)
    assert not bad, "\n".join(bad)
