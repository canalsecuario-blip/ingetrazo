# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""3D Text — real, editable geometry generated from font glyphs (SketchUp's
Texto 3D).

Qt supplies the glyph outlines (``QPainterPath.addText`` →
``toSubpathPolygons``); each outline ring is classified outer/hole by
containment parity, becomes a front face (with holes) and, when a thickness
is given, a back face plus side walls — one closed solid per contour group.
The result is a plain ``Mesh`` for a ``Group``: the letters push/pull, paint
and export like anything drawn by hand.

:func:`make_text_group` is what the app inserts: a container group with ONE
NESTED GROUP PER LETTER (Rafael, 2026-09-16: «que cada letra aparezca como
grupo, como en SketchUp»), carrying the parameters it was made from in
``Group.text3d`` so the text stays EDITABLE — the right-click's «Edit 3D
Text…» reopens the dialog and :func:`rebuild_text_group` lays the letters
out again in place (double-click keeps SketchUp's meaning: it enters).

The text STANDS UP by default: width along +X, height along +Z (base at
z=0), thickness along +Y — so placing it with the component-placement tool
plants the sign on the ground plane.
"""
from __future__ import annotations

from PySide6.QtGui import QFont, QPainterPath, QVector3D

from core.mesh import Mesh

#: Curve flattening happens at font-point scale; 100 pt keeps letter curves
#: smooth without exploding the vertex count.
_FONT_PT = 100.0


def _font(font_family: str, bold: bool, italic: bool) -> QFont:
    font = QFont(font_family)
    font.setPointSizeF(_FONT_PT)
    font.setBold(bold)
    font.setItalic(italic)
    return font


def _rings(text: str, font_family: str, bold: bool, italic: bool,
           x: float = 0.0) -> tuple[list[list[tuple[float, float]]], float]:
    """Glyph outline rings in font units (y already flipped to 'up') and the
    layout height of one line. ``x`` is where the text starts, in font
    units — a single letter of a longer string is drawn at its advance."""
    font = _font(font_family, bold, italic)
    path = QPainterPath()
    path.addText(x, 0.0, font, text)
    rings = []
    for poly in path.toSubpathPolygons():
        ring = [(pt.x(), -pt.y()) for pt in poly]   # Qt y-down → up
        if len(ring) >= 3:
            if ring[0] == ring[-1]:
                ring = ring[:-1]
            if len(ring) >= 3:
                rings.append(ring)
    return rings, _FONT_PT


def _ring_area(ring) -> float:
    s = 0.0
    n = len(ring)
    for i in range(n):
        x0, y0 = ring[i]
        x1, y1 = ring[(i + 1) % n]
        s += x0 * y1 - x1 * y0
    return s / 2.0


def _point_in_ring(pt, ring) -> bool:
    x, y = pt
    inside = False
    n = len(ring)
    for i in range(n):
        x0, y0 = ring[i]
        x1, y1 = ring[(i + 1) % n]
        if (y0 > y) != (y1 > y):
            t = (y - y0) / (y1 - y0)
            if x < x0 + t * (x1 - x0):
                inside = not inside
    return inside


def _group_rings(rings):
    """Pair every ring with its role by containment parity: even depth =
    outer contour, odd = hole of its immediate container."""
    depth = []
    for i, ring in enumerate(rings):
        d = sum(1 for j, other in enumerate(rings)
                if j != i and _point_in_ring(ring[0], other))
        depth.append(d)
    outers = [i for i, d in enumerate(depth) if d % 2 == 0]
    groups = {i: [] for i in outers}
    for i, d in enumerate(depth):
        if d % 2 == 0:
            continue
        container = None
        for j in outers:
            if depth[j] == d - 1 and _point_in_ring(rings[i][0], rings[j]):
                container = j
                break
        if container is not None:
            groups[container].append(i)
    return [(rings[i], [rings[h] for h in holes])
            for i, holes in groups.items()]


def _solid_from_rings(rings, scale: float, y_min: float,
                      thickness: float) -> Mesh:
    """The extruded solid of ``rings`` (font units) at ``scale`` metres per
    unit, its lowest point at ``y_min`` sitting on z=0."""
    mesh = Mesh()

    def V(x, y, side_y: float) -> QVector3D:
        # Font plane (x, up) → world: X = x, Z = up, Y = extrusion depth.
        return QVector3D(x * scale, side_y, (y - y_min) * scale)

    for outer, holes in _group_rings(rings):
        # Windings are set ANALYTICALLY — no orient_outward pass. Its parity
        # probe samples the face centroid, which falls OFF the material on
        # concave glyphs (the classic "L"), misreading exactly those letters.
        # Here the geometry is fully controlled: an outer ring kept CCW in
        # the (x, up) plane maps to a front face whose Newell normal is
        # exactly -Y (toward the viewer), and every wall/back winding follows
        # from it — correct for any glyph, concave or holed.
        if _ring_area(outer) < 0:
            outer = outer[::-1]
        holes = [h if _ring_area(h) < 0 else h[::-1] for h in holes]  # CW

        front_outer = [V(x, y, 0.0) for x, y in outer]
        front_holes = [[V(x, y, 0.0) for x, y in h] for h in holes]
        mesh.add_face(front_outer, hole_loops=front_holes or None)
        if thickness <= 1e-9:
            continue
        back_outer = [V(x, y, thickness) for x, y in outer[::-1]]
        back_holes = [[V(x, y, thickness) for x, y in h[::-1]] for h in holes]
        mesh.add_face(back_outer, hole_loops=back_holes or None)
        for ring_pts in ([outer] + holes):
            n = len(ring_pts)
            for i in range(n):
                x0, y0 = ring_pts[i]
                x1, y1 = ring_pts[(i + 1) % n]
                mesh.add_face([V(x0, y0, 0.0), V(x0, y0, thickness),
                               V(x1, y1, thickness), V(x1, y1, 0.0)])

    # The walls are one quad per outline segment, so the flattened curves of
    # a glyph leave vertical seams along the thickness. Soften wall-to-wall
    # seams at a shallow dihedral (the push/pull curve-facet rule) so the
    # sides read smooth; the front/back outlines (~90°) stay visible.
    for e in mesh.edges:
        if len(e.faces) != 2:
            continue
        n1 = e.faces[0].normal()
        n2 = e.faces[1].normal()
        if (abs(n1.y()) < 0.5 and abs(n2.y()) < 0.5
                and QVector3D.dotProduct(n1, n2) > 0.85):
            e.soft = True
    return mesh


def _block_scale(rings, height: float) -> tuple[float, float]:
    """``(scale, y_min)`` for the whole text block: ``height`` is the REAL
    height of the block (what the engineer asked for), and the lowest point
    sits at z=0 so descenders never dip below the ground the sign is placed
    on."""
    ys = [y for ring in rings for _x, y in ring]
    y_min, y_max = min(ys), max(ys)
    return height / max(y_max - y_min, 1e-9), y_min


def build_text_mesh(text: str, font_family: str = "", bold: bool = False,
                    italic: bool = False, height: float = 0.25,
                    thickness: float = 0.05) -> Mesh:
    """Build the 3D-text mesh in ONE piece: ``height`` is the letter height
    in metres, ``thickness`` the extrusion depth (0 → flat faces only)."""
    rings, _layout_h = _rings(text, font_family, bold, italic)
    if not rings:
        return Mesh()
    scale, y_min = _block_scale(rings, height)
    return _solid_from_rings(rings, scale, y_min, thickness)


def build_text_letters(text: str, font_family: str = "", bold: bool = False,
                       italic: bool = False, height: float = 0.25,
                       thickness: float = 0.05) -> list[tuple[str, Mesh]]:
    """The same text as ONE MESH PER LETTER, ``(character, mesh)`` in
    reading order, spaces and empty glyphs left out. Every letter shares
    the block's scale and baseline, so the letters line up exactly as the
    one-piece build lays them — each simply arrives in its own mesh.

    A glyph is drawn at the advance of the text before it (``QFontMetricsF``
    honours the font's kerning for that prefix), never as a separate string
    at x=0 shifted by hand."""
    from PySide6.QtGui import QFontMetricsF
    rings, _layout_h = _rings(text, font_family, bold, italic)
    if not rings:
        return []
    scale, y_min = _block_scale(rings, height)
    metrics = QFontMetricsF(_font(font_family, bold, italic))
    letters: list = []
    for i, ch in enumerate(text):
        if ch.isspace():
            continue
        x = metrics.horizontalAdvance(text[:i]) if i else 0.0
        glyph, _h = _rings(ch, font_family, bold, italic, x=x)
        if not glyph:
            continue
        mesh = _solid_from_rings(glyph, scale, y_min, thickness)
        if mesh.faces:
            letters.append((ch, mesh))
    return letters


#: The keys ``Group.text3d`` carries — everything the dialog asked for.
TEXT_KEYS = ("text", "font", "bold", "italic", "height", "thickness")


def text_params(text: str, font: str = "", bold: bool = True,
                italic: bool = False, height: float = 0.25,
                thickness: float = 0.05) -> dict:
    return {"text": str(text), "font": str(font or ""), "bold": bool(bold),
            "italic": bool(italic), "height": float(height),
            "thickness": float(thickness)}


def _letter_groups(params: dict, xform=None) -> list:
    """One nested group per letter, each an instance over its own mesh in
    the text's frame — ``xform`` (default identity) is the pose every
    letter starts from."""
    from PySide6.QtGui import QMatrix4x4
    from core.group import Group
    kids = []
    for ch, mesh in build_text_letters(
            params["text"], params.get("font", ""), params.get("bold", True),
            params.get("italic", False), params.get("height", 0.25),
            params.get("thickness", 0.05)):
        g = Group(mesh, name=ch)
        g.xform = QMatrix4x4(xform) if xform is not None else QMatrix4x4()
        kids.append(g)
    return kids


def make_text_group(params: dict):
    """The 3D text as the app inserts it: a container (instance at
    identity, empty mesh of its own) whose children are the letters. Its
    name is the text; ``text3d`` keeps the parameters for later editing.
    ``None`` when the text has no geometry (blank, or a font with nothing
    for those characters)."""
    from core.group import Group
    kids = _letter_groups(params)
    if not kids:
        return None
    g = Group(name=params["text"].strip()[:24])
    g.adopt(kids)
    g.text3d = dict(params)
    return g


def text_frame(group):
    """Where the text sits, as the pose its letters share: entering the
    container pushes its matrix down into the children, so the frame is the
    first letter's matrix, not the container's. Identity when the container
    has no letters yet."""
    from PySide6.QtGui import QMatrix4x4
    kids = getattr(group, "children", None) or ()
    for k in kids:
        if k.xform is not None:
            return QMatrix4x4(k.xform)
    return QMatrix4x4()


def rebuild_text_group(group, params: dict) -> list:
    """The letters for ``params`` laid out where ``group``'s current letters
    are — the new ``children`` list, NOT yet assigned (the command that
    swaps them keeps the old list for undo)."""
    return _letter_groups(params, xform=text_frame(group))
