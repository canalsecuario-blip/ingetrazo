# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""Issue #33 (@pacaeiro): «There's no way of changing Units. Myself, when
doing architecture I work in meters and with mechanical pieces all the
work is in millimeters.» The document carries its units; a bare number is
typed in them and every readout shows them."""
from __future__ import annotations

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import pytest  # noqa: E402
from PySide6.QtGui import QVector3D  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402

if QApplication.instance() is None:
    QApplication([])

from core import units  # noqa: E402
from core.scene import Scene  # noqa: E402
from formats import igz  # noqa: E402


@pytest.fixture
def bound():
    scene = Scene()
    units.bind_scene(scene)
    yield scene
    units.bind_scene(None)


def test_readouts_follow_the_models_units(bound):
    assert units.fmt_len(2.5) == "2.50 m"
    assert units.fmt_pair(3.0, 2.0) == "3.00 × 2.00 m"
    assert units.fmt_area(4.0) == "4.00 m²"
    bound.units = {"length": "mm", "precision": 0}
    assert units.fmt_len(2.5) == "2500 mm"
    assert units.fmt_pair(3.0, 2.0) == "3000 × 2000 mm"
    assert units.fmt_area(4.0) == "4000000 mm²"
    bound.units = {"length": "cm", "precision": 1}
    assert units.fmt_len(0.256) == "25.6 cm"
    bound.units = {"length": "ft-in", "precision": 0}
    assert units.fmt_len(0.3048 * 2 + 0.0254 * 6) == "2'6\""
    assert units.fmt_area(0.3048 ** 2) == "1 ft²"


def test_a_bare_number_is_typed_in_the_models_unit(bound):
    from views.viewport import _parse_length_field
    assert abs(_parse_length_field("2") - 2.0) < 1e-9
    bound.units = {"length": "mm", "precision": 0}
    assert abs(_parse_length_field("2") - 0.002) < 1e-12
    assert abs(_parse_length_field("2m") - 2.0) < 1e-9          # an explicit unit still wins
    assert abs(_parse_length_field("-30") + 0.030) < 1e-12
    bound.units = {"length": "ft-in", "precision": 0}
    assert abs(_parse_length_field("6") - 6 * 0.0254) < 1e-9     # inches, as SketchUp


def test_units_travel_in_the_igz_and_default_to_metres(tmp_path):
    scene = Scene()
    scene.units = {"length": "mm", "precision": 1}
    path = tmp_path / "mm.igz"
    igz.save_scene(scene, path)
    back = Scene()
    igz.load_into(back, path)
    assert back.units == {"length": "mm", "precision": 1}
    plain = Scene()
    igz.save_scene(plain, tmp_path / "m.igz")
    import json
    doc = json.loads((tmp_path / "m.igz").read_text(encoding="utf-8"))
    assert "units" not in doc["scene"]                     # the default is silent
    again = Scene()
    igz.load_into(again, tmp_path / "m.igz")
    assert again.units == {"length": "m", "precision": 2}
    scene.clear()
    assert scene.units == {"length": "m", "precision": 2}


def test_a_tool_label_reads_in_the_models_units(bound):
    from tools.rectangle import RectangleTool
    t = RectangleTool()
    t.start_point = QVector3D(0, 0, 0)
    t.hover_point = QVector3D(5, 4, 0)
    assert t.value_label()[0] == "5.00 × 4.00 m"
    bound.units = {"length": "cm", "precision": 0}
    assert t.value_label()[0] == "500 × 400 cm"


def test_the_viewport_binds_its_scene_and_the_dialog_reads_it():
    from views.viewport import Viewport
    vp = Viewport(None)
    assert units.model_units_of(vp.scene) == {"length": "m", "precision": 2}
    vp.scene.units = {"length": "in", "precision": 1}
    assert units.fmt_len(0.0254) == '1.0"'
    units.bind_scene(None)
