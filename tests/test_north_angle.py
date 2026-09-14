# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""North angle (SketchUp's): the map turns under the model, never the model
under the map — and StraightenModelCommand, which converts a model that was
turned+dragged onto its site into exactly that.

Marco, 2026-09-14: the plaza was drawn square to the axes, then rotated ~33°
and dragged onto the satellite map to georeference it — and the front/right
views, drawn to the axes, stopped meaning anything."""
from __future__ import annotations

import math

from PySide6.QtGui import QMatrix4x4, QVector3D

from core.dimension import Dimension
from core.group import Group
from core.history import History, StraightenModelCommand, placement_rotation_deg
from core.mesh import Mesh
from core.saved_views import SavedView
from core.scene import Scene
from formats import igz
from georef.datum import SceneDatum
from georef.tiles import PRESETS, DEFAULT_SOURCE_ID, TileLayer

YANQUE = (-15.459809, -72.947774)


def _close(a, b, tol=1e-3):
    return abs(a.x() - b.x()) < tol and abs(a.y() - b.y()) < tol and abs(a.z() - b.z()) < tol


# ---- Datum ---------------------------------------------------------------------

def test_north_angle_turns_the_grid_under_the_model():
    plain = SceneDatum(*YANQUE)
    lat, lon, _ = plain.local_to_geodetic(QVector3D(0.0, 10.0, 0.0))  # 10 m north
    east = SceneDatum(*YANQUE, north=90.0)      # north lies along +X
    p = east.geodetic_to_local(lat, lon)
    assert _close(p, QVector3D(10.0, 0.0, 0.0))
    assert _close(east.north_vector(), QVector3D(1.0, 0.0, 0.0))
    # and the way back
    back = east.local_to_geodetic(p)
    assert abs(back[0] - lat) < 1e-9 and abs(back[1] - lon) < 1e-9


def test_north_angle_round_trips_utm_and_wraps():
    d = SceneDatum(*YANQUE, north=33.5)
    p = QVector3D(12.0, -7.0, 3.0)
    e, n, a = d.local_to_utm(p)
    assert _close(d.utm_to_local(e, n, a), p, 1e-6)
    assert SceneDatum(0, 0, north=350.0).north == -10.0
    assert SceneDatum(0, 0, north=-180.0).north == 180.0


def test_north_angle_persists_in_igz_and_stays_terse_at_zero(tmp_path):
    scene = Scene()
    scene.add_edge(QVector3D(0, 0, 0), QVector3D(1, 0, 0))
    scene.georef = SceneDatum(*YANQUE, north=33.47)
    path = tmp_path / "north.igz"
    igz.save_scene(scene, path)
    loaded = Scene()
    igz.load_into(loaded, path)
    assert abs(loaded.georef.north - 33.47) < 1e-9

    assert "north" not in SceneDatum(*YANQUE).to_dict()   # older readers: nothing new


def test_tile_quads_turn_with_the_north_angle():
    layer = TileLayer(PRESETS[DEFAULT_SOURCE_ID], zoom=18)
    x, y = layer.visible_tiles(SceneDatum(*YANQUE))[0]
    quad = layer.quad_local(SceneDatum(*YANQUE, north=90.0), x, y)
    nw, ne = quad[0][0], quad[1][0]
    edge = ne - nw                       # the tile's north edge runs east…
    assert edge.x() < 1e-6 and edge.y() < 0   # …which now lies along -Y


# ---- Straighten ------------------------------------------------------------------

def _placement(deg: float, tx: float, ty: float, tz: float = 0.0) -> QMatrix4x4:
    m = QMatrix4x4()
    m.translate(QVector3D(tx, ty, tz))
    m.rotate(deg, QVector3D(0, 0, 1))
    return m


def _placed_scene():
    """A square plaza drawn on the axes, then turned 33.47° and dragged onto
    the site (one top-level instance), plus a loose edge, a classic group, a
    dimension and a saved view — everything that must ride along."""
    scene = Scene()
    scene.georef = SceneDatum(*YANQUE)
    proto = Mesh()
    proto.add_face([QVector3D(0, 0, 0), QVector3D(36, 0, 0),
                    QVector3D(36, 20, 0), QVector3D(0, 20, 0)])
    plaza = Group(proto, "Plaza")
    plaza.xform = _placement(33.47, -5.1872, -37.3379)
    scene.groups.append(plaza)
    classic = Group(Mesh(), "Banca")
    classic.mesh.add_face([QVector3D(1, 1, 0), QVector3D(2, 1, 0),
                           QVector3D(2, 2, 0), QVector3D(1, 2, 0)])
    scene.groups.append(classic)
    scene.add_edge(QVector3D(0, 0, 0), QVector3D(0, 0, 5))
    scene.dimensions.append(Dimension(QVector3D(0, 0, 0), QVector3D(36, 0, 0),
                                      QVector3D(0, -2, 0)))
    scene.saved_views.append(SavedView("Frente", target=(18.0, 10.0, 0.0),
                                       yaw=-math.pi / 2, pitch=0.0))
    return scene, plaza, classic


def _geo(datum, p):
    lat, lon, _ = datum.local_to_geodetic(p)
    return lat, lon


def test_placement_rotation_reads_a_turn_and_refuses_tilt_or_scale():
    assert abs(placement_rotation_deg(_placement(33.47, 1, 2)) - 33.47) < 1e-4
    tilted = QMatrix4x4()
    tilted.rotate(10, QVector3D(1, 0, 0))
    scaled = QMatrix4x4()
    scaled.scale(2.0)
    for bad in (tilted, scaled):
        try:
            placement_rotation_deg(bad)
        except ValueError:
            pass
        else:
            raise AssertionError("expected ValueError")


def test_straighten_puts_the_model_on_its_axes_and_turns_the_map():
    scene, plaza, classic = _placed_scene()
    old = scene.georef
    # Where things stand on the EARTH before — that must not change.
    corner_before = _geo(old, plaza.xform.map(QVector3D(36, 20, 0)))
    banca_before = _geo(old, QVector3D(1, 1, 0))
    dim_before = _geo(old, scene.dimensions[0].b)
    view_before = _geo(old, QVector3D(18.0, 10.0, 0.0))

    hist = History(scene)
    hist.execute(StraightenModelCommand(plaza))
    assert hist.last_error is None

    new = scene.georef
    assert new is not old
    assert abs(new.north - 33.47) < 1e-4
    assert plaza.xform.isIdentity()           # square to the axes again
    # Same ground under everything: the plaza corner, the classic group, the
    # dimension and the saved view's target all sit on the same lat/lon.
    for before, after in (
            (corner_before, _geo(new, QVector3D(36, 20, 0))),
            (banca_before, _geo(new, classic.mesh.vertices[0].position)),
            (dim_before, _geo(new, scene.dimensions[0].b)),
            (view_before, _geo(new, QVector3D(*scene.saved_views[0].target)))):
        assert abs(before[0] - after[0]) < 1e-9
        assert abs(before[1] - after[1]) < 1e-9
    # The saved view turned with the model.
    assert abs(scene.saved_views[0].yaw - (-math.pi / 2 - math.radians(33.47))) < 1e-6
    # The dimension offset is a direction: turned, not translated.
    off = scene.dimensions[0].offset
    assert abs(off.length() - 2.0) < 1e-6

    # And undo puts every bit back.
    assert hist.undo() is True
    assert scene.georef is old
    assert _close(plaza.xform.map(QVector3D(0, 0, 0)),
                  QVector3D(-5.1872, -37.3379, 0.0))
    assert _close(classic.mesh.vertices[0].position, QVector3D(1, 1, 0))
    assert _close(scene.dimensions[0].offset, QVector3D(0, -2, 0))
    assert abs(scene.saved_views[0].yaw - (-math.pi / 2)) < 1e-12
    assert hist.redo() is True
    assert plaza.xform.isIdentity() and abs(scene.georef.north - 33.47) < 1e-4


def test_straighten_refuses_without_a_location_or_a_placed_component():
    scene, plaza, classic = _placed_scene()
    scene.georef = None
    hist = History(scene)
    hist.execute(StraightenModelCommand(plaza))
    assert hist.last_error and "location" in hist.last_error
    scene.georef = SceneDatum(*YANQUE)
    hist.execute(StraightenModelCommand(classic))     # no placement to undo
    assert hist.last_error and "placed" in hist.last_error
    assert scene.georef.north == 0.0


# ---- Tray -----------------------------------------------------------------------

def test_tray_north_field_retargets_the_datum_and_refreshes_the_map():
    """Typing a north angle swaps in a NEW datum (tile geometry is cached
    by datum identity) and asks the viewport for fresh tiles."""
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance() or QApplication([])   # noqa: F841
    from views.tray import BaseMapPanel

    class _Viewport:
        scene = Scene()
        resets = 0

        def reset_tiles(self):
            self.resets += 1

        def notify_scene_changed(self):
            pass

    class _Win:
        viewport = _Viewport()

    win = _Win()
    win.viewport.scene.georef = SceneDatum(*YANQUE)
    panel = BaseMapPanel(win)
    panel._sync_from_scene()
    assert panel._north.value() == 0.0
    old = win.viewport.scene.georef
    panel._north.setValue(33.5)
    panel._on_north_edited()
    new = win.viewport.scene.georef
    assert new is not old and abs(new.north - 33.5) < 1e-9
    assert (new.lat, new.lon, new.alt) == (old.lat, old.lon, old.alt)
    assert win.viewport.resets == 1
    panel._on_north_edited()                  # same value: nothing happens
    assert win.viewport.scene.georef is new and win.viewport.resets == 1


def test_placement_is_identity_spots_a_group_that_was_never_turned():
    """The Straighten button on a group at identity is a silent no-op —
    Marco pressed it eleven times on the DWG instead of the plaza he had
    turned (2026-09-14); the panel now says which group to pick."""
    from core.history import placement_is_identity
    assert placement_is_identity(None)
    assert placement_is_identity(QMatrix4x4())
    turned = QMatrix4x4()
    turned.rotate(2.5, 0.0, 0.0, 1.0)
    assert not placement_is_identity(turned)
    moved = QMatrix4x4()
    moved.translate(0.0, 0.0, -3182.0)
    assert not placement_is_identity(moved)
