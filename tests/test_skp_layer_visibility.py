# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""A layer switched off in the .skp arrives switched off.

openskp's ``Layer`` carries ``hidden``; the adapter asked it for
``visible``, which no generation of the library has ever had. So
``getattr(ly, "visible", True)`` fell through to its default on every file
and EVERY imported layer landed visible, whatever the author had turned
off.

Found on 2026-09-17 with Rafael's ``edificio.skp``: the file hides
``Camera_FOV_Lines`` and ``Camera_FOV_Volume``, so SketchUp shows a small
camera glyph and nothing else. IngeTrazo drew the whole camera frustum
across the model — Marco spotted it comparing screenshots side by side.

Not a regression from the openskp 1.3.0 repin: the old pinned version
spelled it ``hidden`` too. It had simply never worked.
"""
from __future__ import annotations

from dataclasses import dataclass

from formats.skp_openskp import file_layer_records


@dataclass
class _Layer:
    """openskp's Layer, as far as this matters."""
    name: str
    hidden: bool = False
    color_r: int = 200
    color_g: int = 200
    color_b: int = 200


class _Node:
    def __init__(self):
        self.faces, self.edges, self.vertices = {}, {}, {}
        self.instances, self.dimensions, self.texts = [], [], []
        self.section_planes = []
        self.name, self.guid = "", ""
        self.always_faces_camera = False
        self.is_image = False


class _Model:
    def __init__(self, layers):
        self.layers = layers
        self.root = _Node()
        self.definitions = {}
        self.materials, self.materials_by_id = [], {}
        self.pages, self.styles, self.dimensions = [], [], []
        self.version = "{20.0.000}"
        self.units = None


def _layers_of(model):
    return {d["name"]: d["visible"] for d in file_layer_records(model)}


def test_a_hidden_layer_arrives_hidden():
    got = _layers_of(_Model([
        _Layer("Cameras", hidden=False),
        _Layer("Camera_FOV_Lines", hidden=True),
        _Layer("Camera_FOV_Volume", hidden=True),
    ]))
    assert got == {"Cameras": True,
                   "Camera_FOV_Lines": False,
                   "Camera_FOV_Volume": False}


def test_a_plain_layer_is_still_visible():
    assert _layers_of(_Model([_Layer("Muros"), _Layer("Techos")])) == {
        "Muros": True, "Techos": True}


def test_the_default_layer_still_does_not_travel():
    """``Layer0`` IS IngeTrazo's default layer; importing it would make a
    duplicate. Pinned so the visibility fix does not let it through."""
    got = _layers_of(_Model([_Layer("Layer0"), _Layer("Untagged"),
                             _Layer("Muros")]))
    assert got == {"Muros": True}


def test_a_library_that_said_visible_would_still_be_understood():
    """Belt and braces: no openskp has ever exposed ``visible``, but if one
    ever does, it must not be read as hidden."""
    @dataclass
    class _Old:
        name: str
        visible: bool = True

    assert _layers_of(_Model([_Old("Muros", visible=False),
                              _Old("Techos", visible=True)])) == {
        "Muros": False, "Techos": True}
