# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""Linear dimension — a measured annotation between two world points.

A ``Dimension`` records two endpoints ``a``/``b`` and an ``offset`` vector
giving where the dimension line sits relative to the measured segment.

An endpoint placed ON a vertex is **anchored** to it (SketchUp attaches a
dimension to the geometry it measures): the endpoint reads the vertex's
position live, so scaling, moving or stretching the drawing takes the
dimension along and re-measures it — the first thing a user of DriveMeca's
video missed (2026-09-20, Marco: «dibujamos algo, lo acotamos, después lo
escalamos y la acotación se queda allí, no se redimensiona con el dibujo
y no se actualiza la nueva medición»). A vertex inside a component reads
through its placement's transform, so moving the instance moves the
dimension too. When the vertex is gone (erased, welded away) the endpoint
freezes where it last was. An endpoint snapped to a midpoint, an edge or a
face has no vertex to hold and stays static.

It is an annotation, not geometry: it lives in ``Scene.dimensions`` and is
drawn as a screen-space overlay (extension lines + dimension line + value
label), not in the mesh.
"""
from __future__ import annotations

from PySide6.QtGui import QMatrix4x4, QVector3D


class VertexAnchor:
    """A hold on one mesh vertex: the vertex, the mesh that registers it
    (to notice when it is gone) and the chain of groups whose transforms
    place it in the world — empty for loose geometry, ``[group]`` for a
    classic group, ``[component, child, …]`` down a nested placement."""

    __slots__ = ("vertex", "mesh", "chain")

    def __init__(self, vertex, mesh, chain=()) -> None:
        self.vertex = vertex
        self.mesh = mesh
        self.chain = tuple(chain)

    def matrix(self):
        """The composed placement transform, or ``None`` when every group
        on the chain keeps its geometry in world coordinates."""
        m = None
        for g in self.chain:
            x = getattr(g, "xform", None)
            if x is None:
                continue
            m = QMatrix4x4(x) if m is None else m * x
        return m

    def position(self):
        """The vertex's world position now — ``None`` once the mesh no
        longer registers this very vertex (erased, or welded into another
        one) or nothing references it any more, which is the anchor's cue
        to let go."""
        v = self.vertex
        try:
            if self.mesh.vertex_at(v.position) is not v or not v.edges:
                return None
        except Exception:  # noqa: BLE001 — a mesh that cannot answer
            return None
        m = self.matrix()
        return m.map(QVector3D(v.position)) if m is not None \
            else QVector3D(v.position)


def resolve_vertex_anchor(scene, point: QVector3D, tol: float = 1e-4):
    """The vertex sitting at *point* (world), as a :class:`VertexAnchor`,
    or ``None``. Loose geometry first, then every group placement, the
    point taken back into each placement's local coordinates — O(1) per
    mesh through the vertex registry, so a click costs nothing on a big
    model. ``tol`` is the registry's own weld resolution (0.1 mm): a
    point that came through a placement's float32 matrix and back lands
    within a micron of the vertex, which a tighter tolerance rejected on
    far-out coordinates."""
    from core.group import iter_placements

    def hit(mesh, local, chain):
        v = mesh.vertex_at(local)
        if v is None or (v.position - local).length() > tol:
            return None
        if not v.edges:
            # An orphan: a vertex nothing references any more. Make Group
            # moves the geometry into the group's mesh and leaves these
            # behind in the loose one, at the very same spots — so a
            # dimension on a fresh group anchored to the ghost, and the
            # group scaled away from under it (Marco, 2026-09-20: «faltaba
            # en grupo»). A point held by nothing holds nothing.
            return None
        return VertexAnchor(v, mesh, chain)

    found = hit(scene.mesh, QVector3D(point), ())
    if found is not None:
        return found
    for g in getattr(scene, "groups", None) or ():
        if getattr(g, "billboard", False):
            continue
        for placed, m in iter_placements(g):
            local = QVector3D(point)
            chain = _chain_to(g, placed)
            if m is not None:
                inv, ok = m.inverted()
                if not ok:
                    continue
                local = inv.map(local)
            found = hit(placed.mesh, local, chain)
            if found is not None:
                return found
    return None


def _chain_to(root, target) -> tuple:
    """The groups from *root* down to *target* (inclusive) — the transforms
    an anchor composes. Depth-first, like ``iter_placements``."""
    if root is target:
        return (root,)
    for child in getattr(root, "children", None) or ():
        below = _chain_to(child, target)
        if below:
            return (root,) + below
    return ()


class Dimension:
    """See the module docstring. ``a`` and ``b`` read live through their
    anchors; assigning them sets the frozen position (what a rigid
    transform of the whole model does) and keeps the anchor."""

    def __init__(self, a: QVector3D, b: QVector3D, offset: QVector3D,
                 layer: str | None = None, text: str | None = None) -> None:
        self._a = QVector3D(a)
        self._b = QVector3D(b)
        #: displacement from the a–b segment to the dimension line
        self.offset = QVector3D(offset)
        #: Layer (SketchUp tag) the annotation lives on; ``None`` = default
        #: layer. Scenes hide layers, so a plan scene can show a clean model
        #: and an "Anotaciones" layer can carry the cotas and leader texts.
        self.layer = layer
        #: Custom text (SketchUp: double-click the value to edit it);
        #: ``None`` shows the measured value, and ``<>`` inside the text
        #: stands for it.
        self.text = text
        self.anchor_a: VertexAnchor | None = None
        self.anchor_b: VertexAnchor | None = None

    # ---- endpoints ----------------------------------------------------------
    def _live(self, which: str) -> QVector3D:
        anchor = getattr(self, "anchor_" + which)
        if anchor is not None:
            p = anchor.position()
            if p is None:                    # the vertex is gone: freeze
                setattr(self, "anchor_" + which, None)
            else:
                setattr(self, "_" + which, p)
        return getattr(self, "_" + which)

    @property
    def a(self) -> QVector3D:
        return self._live("a")

    @a.setter
    def a(self, value: QVector3D) -> None:
        self._a = QVector3D(value)

    @property
    def b(self) -> QVector3D:
        return self._live("b")

    @b.setter
    def b(self, value: QVector3D) -> None:
        self._b = QVector3D(value)

    def bind(self, scene) -> None:
        """Anchor each endpoint to the vertex under it, if there is one —
        at placement, and again when a document is opened (the .igz keeps
        positions, and the vertex at that very position is the one the
        drafter snapped to)."""
        self.anchor_a = resolve_vertex_anchor(scene, self._a)
        self.anchor_b = resolve_vertex_anchor(scene, self._b)

    @property
    def anchored(self) -> bool:
        """Both endpoints held by vertices."""
        return self.anchor_a is not None and self.anchor_b is not None

    def anchor_points(self) -> list:
        """The world positions of the anchored endpoints (0, 1 or 2)."""
        return [p for p, an in ((self.a, self.anchor_a), (self.b, self.anchor_b))
                if an is not None]

    # ---- geometry -----------------------------------------------------------
    def display_text(self, measured: str) -> str:
        """What the annotation shows: the custom text with ``<>`` swapped
        for the formatted measurement, or the measurement itself."""
        if self.text:
            return self.text.replace("<>", measured)
        return measured

    def value(self) -> float:
        """Measured length (metres)."""
        return (self.b - self.a).length()

    def label(self) -> str:
        return f"{self.value():.2f} m"

    def perpendicular_offset(self) -> QVector3D:
        """The offset with any component ALONG the measured segment
        removed: the geometry may have turned under an anchored dimension
        since it was placed, and the extension lines must stay square to
        the line (the line itself is parallel to a–b whatever the offset)."""
        ab = self.b - self.a
        length = ab.length()
        if length < 1e-9:
            return QVector3D(self.offset)
        dir_ = ab / length
        along = QVector3D.dotProduct(self.offset, dir_)
        return self.offset - dir_ * along

    def line_points(self) -> tuple[QVector3D, QVector3D]:
        """The dimension line's endpoints (``a``/``b`` shifted by the offset)."""
        off = self.perpendicular_offset()
        return self.a + off, self.b + off

    def midpoint(self) -> QVector3D:
        ap, bp = self.line_points()
        return (ap + bp) * 0.5

    @staticmethod
    def offset_for_cursor(a: QVector3D, b: QVector3D,
                          cursor: QVector3D) -> QVector3D:
        """Offset placing the dimension line through ``cursor`` while staying
        parallel to ``a``–``b``: the component of ``cursor − a`` perpendicular
        to the segment direction."""
        ab = b - a
        length = ab.length()
        if length < 1e-9:
            return cursor - a
        dir_ = ab / length
        to_cursor = cursor - a
        along = QVector3D.dotProduct(to_cursor, dir_)
        return to_cursor - dir_ * along
