# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""SketchUp's Hide on OBJECTS (groups and components), and scenes that
remember it.

Rafael, 2026-09-16 (38:40): «yo lo que quería hacer era una escena en
donde esto esté oculto… no sé si tenemos opción de ocultar un elemento.
Tiene ocultar aristas, pero no sé si tenemos opción de ocultar un objeto
en concreto». There was none: only edges, and the rest of the model while
editing.
"""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtGui import QGuiApplication, QMatrix4x4, QVector3D

_app = QGuiApplication.instance() or QGuiApplication([])

from core.group import Group, copy_group
from core.history import HideCommand, HideEdgesCommand, History
from core.mesh import Mesh
from core.saved_views import SavedView
from core.scene import Scene
from formats import igz


def _box(mesh, x0=0.0, y0=0.0, s=1.0, h=1.0):
    P = [QVector3D(x0 + s * (i & 1), y0 + s * ((i >> 1) & 1), h * (i >> 2))
         for i in range(8)]
    for q in ([0, 2, 3, 1], [4, 5, 7, 6], [0, 1, 5, 4], [2, 6, 7, 3],
              [0, 4, 6, 2], [1, 3, 7, 5]):
        mesh.add_face([P[i] for i in q])
    return mesh


def _group(name="caja", x0=0.0):
    return Group(_box(Mesh(), x0=x0), name=name)


def test_hide_command_takes_the_object_out_of_sight_and_undo_brings_it_back():
    scene = Scene()
    history = History(scene)
    g = _group()
    scene.groups.append(g)
    scene.select([g])
    assert scene.entity_visible(g) and scene.entity_selectable(g)

    history.execute(HideCommand([g]))
    assert g.hidden
    assert not scene.entity_visible(g) and not scene.entity_selectable(g)
    assert g not in scene.selection            # nothing invisible stays selected
    assert scene.bounds()[0] is None           # gone from the extents too

    history.undo()
    assert not g.hidden and scene.entity_visible(g)
    history.redo()
    assert g.hidden


def test_hide_command_also_hides_edges_and_ignores_faces():
    scene = Scene()
    history = History(scene)
    _box(scene.mesh)
    edge = scene.mesh.edges[0]
    face = scene.mesh.faces[0]
    history.execute(HideCommand([edge, face]))
    assert edge.hidden
    assert "hidden" not in face.attrs          # faces are not this command's
    # the edges-only spelling still works (the Eraser uses it)
    history.execute(HideEdgesCommand([edge], hidden=False))
    assert not edge.hidden


def test_hidden_flag_and_uid_round_trip_through_igz(tmp_path):
    scene = Scene()
    g1, g2 = _group("a"), _group("b", x0=3.0)
    g2.hidden = True
    scene.groups += [g1, g2]
    p = tmp_path / "oculto.igz"
    igz.save_scene(scene, p)
    scene2 = Scene()
    igz.load_into(scene2, p)
    back = {g.name: g for g in scene2.groups}
    assert not back["a"].hidden and back["b"].hidden
    assert back["a"].uid == g1.uid and back["b"].uid == g2.uid


def test_every_group_gets_its_own_uid_and_a_copy_a_new_one():
    g = _group()
    c = copy_group(g)
    assert g.uid and c.uid and g.uid != c.uid
    assert len(g.uid) == 16
    g.hidden = True
    assert copy_group(g).hidden


def test_a_scene_remembers_which_objects_are_hidden():
    from types import SimpleNamespace
    scene = Scene()
    g1, g2 = _group("a"), _group("b", x0=3.0)
    scene.groups += [g1, g2]
    cam = SimpleNamespace(target=QVector3D(0, 0, 0), distance=10.0, yaw=0.5,
                          pitch=0.4, fov_deg=45.0, perspective=True)
    g2.hidden = True
    view = SavedView.capture("sin caja b", scene, cam)
    assert view.hidden_objects == [g2.uid]

    g2.hidden = False
    g1.hidden = True
    view.apply(scene, cam)
    assert g2.hidden and not g1.hidden          # exactly what was saved

    # …and it survives the document.
    raw = view.to_dict()
    assert raw["hidden_objects"] == [g2.uid]
    again = SavedView.from_dict(raw)
    assert again.hidden_objects == [g2.uid]


def test_a_scene_from_before_this_field_leaves_hidden_objects_alone():
    from types import SimpleNamespace
    scene = Scene()
    g = _group()
    scene.groups.append(g)
    cam = SimpleNamespace(target=QVector3D(0, 0, 0), distance=10.0, yaw=0.5,
                          pitch=0.4, fov_deg=45.0, perspective=True)
    old = SavedView.from_dict({"name": "vieja", "target": [0, 0, 0],
                               "distance": 10.0, "yaw": 0.0, "pitch": 0.3})
    assert old.hidden_objects is None
    g.hidden = True
    old.apply(scene, cam)
    assert g.hidden                              # hands-off


def test_hiding_a_container_hides_its_nested_placements_in_the_viewport():
    from views.main_window import MainWindow
    win = MainWindow()
    win.show()
    _app.processEvents()
    vp = win.viewport
    try:
        letter = _group("hoja")
        letter.xform = QMatrix4x4()
        container = Group(name="arbol")
        container.adopt([letter])
        vp.scene.groups.append(container)
        vp.scene.version += 1
        proxies = [g for g in vp._placements() if g.owner is container]
        assert proxies and not any(p.hidden for p in proxies)

        vp.history.execute(HideCommand([container]))
        proxies = [g for g in vp._placements() if g.owner is container]
        assert proxies and all(p.hidden for p in proxies)
        assert all(not vp.scene.entity_visible(p) for p in proxies)
        img = vp.render_image(160, 120, overlays=False)   # still paints
        assert img is not None and not img.isNull()

        # a child hidden on its own stays hidden inside a visible parent
        vp.history.undo()
        vp.history.execute(HideCommand([letter]))
        proxies = [g for g in vp._placements() if g.owner is container]
        assert all(p.hidden for p in proxies)
        assert vp.scene.entity_visible(container)
    finally:
        win._saved_version = vp.scene.version
        win.close()


def test_edit_menu_hide_unhide_last_and_all():
    from views.main_window import MainWindow
    win = MainWindow()
    win.show()
    _app.processEvents()
    vp = win.viewport
    try:
        a, b = _group("a"), _group("b", x0=3.0)
        vp.scene.groups += [a, b]
        _box(vp.scene.mesh, x0=6.0)
        edge = vp.scene.mesh.edges[0]
        vp.scene.version += 1

        vp.scene.select([a])
        win._on_hide()
        assert a.hidden and not b.hidden
        vp.scene.select([b, edge])
        win._on_hide()
        assert b.hidden and edge.hidden

        win._on_unhide_last()                      # the second Hide comes back
        assert not b.hidden and not edge.hidden and a.hidden
        win._on_unhide_last()
        assert not a.hidden
        assert win._hidden_everywhere() == []

        vp.scene.select([a, b])
        win._on_hide()
        win._on_unhide_all()
        assert not a.hidden and not b.hidden
        vp.history.undo()                          # Unhide All is one step
        assert a.hidden and b.hidden
    finally:
        win._saved_version = vp.scene.version
        win.close()
