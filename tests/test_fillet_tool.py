# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""The Fillet tool: click an edge, size the radius with the cursor or the
VCB, click (or Enter) to round it — one undo step; the selection's edges
are rounded together; refusals only speak."""
from __future__ import annotations

import pytest
from PySide6.QtCore import QPointF, Qt
from PySide6.QtGui import QVector3D
from PySide6.QtWidgets import QApplication

from core.orient import is_closed
from tools.base import ToolContext
from tools.fillet import FilletTool
from tests.test_fillet import box, edge_at


@pytest.fixture(scope="module")
def viewport():
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    elif not isinstance(app, QApplication):
        pytest.skip("another Qt application flavour is already running")
    from views.viewport import Viewport
    vp = Viewport(None)
    vp.resize(1000, 700)
    vp.camera.set_aspect(1000, 700)
    vp.flash_status = lambda *a, **k: None
    return vp


def _box_scene(vp):
    vp.scene.mesh.clear()
    vp.history.undo_stack.clear()
    vp.history.redo_stack.clear()
    src = box()
    for f in src.faces:
        vp.scene.mesh.add_face(f.vertices)
    vp.scene.version += 1
    return vp.scene.mesh


def _ctx(vp, world):
    return ToolContext(viewport=vp, world=QVector3D(*world), screen=QPointF(0, 0),
                       modifiers=Qt.NoModifier, snap=None)


def test_click_edge_size_with_the_cursor_click_to_round(viewport):
    mesh = _box_scene(viewport)
    tool = FilletTool()
    FilletTool.radius = 0.1
    viewport.set_active_tool(tool)
    e = edge_at(mesh, (0, 0, 1), (2, 0, 1))
    viewport._hover_edge = e
    tool.on_hover(_ctx(viewport, (1, 0, 1)))
    assert tool.hover_edge is e
    assert len(tool.preview_faces()) == 8            # live preview at 0.1
    tool.on_click(_ctx(viewport, (1, 0, 1)))
    assert tool.sizing and tool.edges == [e]
    # The cursor 0.25 from the edge (on the top face) sets the radius.
    tool.on_hover(_ctx(viewport, (1.0, 0.25, 1.0)))
    assert FilletTool.radius == pytest.approx(0.25)
    assert tool.value_label()[0].startswith("R 0.250")
    depth = len(viewport.history.undo_stack)
    tool.on_click(_ctx(viewport, (1.0, 0.25, 1.0)))
    assert len(viewport.history.undo_stack) == depth + 1
    assert len(mesh.faces) == 6 + 8 and is_closed(mesh)
    assert not tool.sizing and not tool.edges
    viewport.history.undo()
    assert len(mesh.faces) == 6 and len(mesh.edges) == 12
    viewport.history.redo()
    assert len(mesh.faces) == 14


def test_a_typed_radius_rounds_the_selected_edges(viewport):
    mesh = _box_scene(viewport)
    rim = [edge_at(mesh, (0, 0, 1), (2, 0, 1)), edge_at(mesh, (2, 0, 1), (2, 1, 1)),
           edge_at(mesh, (2, 1, 1), (0, 1, 1)), edge_at(mesh, (0, 1, 1), (0, 0, 1))]
    viewport.scene.select(rim)
    tool = FilletTool()
    viewport.set_active_tool(tool)
    assert set(tool.edges) == set(rim)                # the selection is the set
    assert tool.on_segments_value(viewport, 6)
    assert tool.on_value(viewport, 0.15)
    assert len(mesh.faces) == 6 + 4 * 6 and is_closed(mesh)
    assert not viewport.scene.selection
    assert FilletTool.radius == pytest.approx(0.15)


def test_a_refused_rounding_only_speaks(viewport):
    mesh = _box_scene(viewport)
    said = []
    viewport.flash_status = lambda text, *a, **k: said.append(text)
    tool = FilletTool()
    viewport.set_active_tool(tool)
    viewport._hover_edge = edge_at(mesh, (0, 0, 1), (2, 0, 1))
    tool.on_hover(_ctx(viewport, (1, 0, 1)))
    tool.on_click(_ctx(viewport, (1, 0, 1)))
    assert not tool.on_value(viewport, -1.0)
    assert tool.on_value(viewport, 5.0)               # far too big for the box
    assert len(mesh.faces) == 6
    assert any("too large" in s or "collapse" in s for s in said)
    viewport.flash_status = lambda *a, **k: None
    tool.on_cancel(viewport)
    assert not tool.edges
