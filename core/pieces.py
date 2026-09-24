# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""Split a group into its physical pieces: the solids that do not touch.

What a model file calls its parts is often not what a person would. A Sweet
Home 3D bar stool is 43 groups in its OBJ, and they are surface fragments —
cut wherever the material changes — while the stool itself is five things
you could pick up: the seat with its back, a footrest, a front frame and two
side legs. Connectivity is what tells them apart: faces that share a vertex
belong to one piece, and a piece that shares nothing with the rest is a part
on its own.

The limit is the same one the eye has on a welded mesh: two parts that were
modelled touching, sharing vertices, read as one piece.
"""
from __future__ import annotations

from core.mesh import Mesh, edge_flags, stamp_edge_flags


def connected_parts(mesh: Mesh) -> list:
    """``mesh`` cut into its connected pieces, each a ``(faces, edges)``
    pair, largest first (by face count, a loose wire after every solid).

    Two faces are one piece when they share a vertex; a loose edge joins
    whatever its ends touch, so a wire hanging off a solid stays with it."""
    parent: dict = {}

    def find(x):
        root = x
        while parent.get(root, root) != root:
            root = parent[root]
        while parent.get(x, x) != root:        # flatten the path behind us
            parent[x], x = root, parent[x]
        return root

    def join(vs) -> None:
        r = find(id(vs[0]))
        for v in vs[1:]:
            k = find(id(v))
            if k != r:
                parent[k] = r

    for f in mesh.faces:
        join(list(f.loop) + [v for h in f.hole_loops for v in h])
    for e in mesh.edges:
        join([e.v0, e.v1])

    parts: dict = {}
    for f in mesh.faces:
        parts.setdefault(find(id(f.loop[0])), ([], []))[0].append(f)
    for e in mesh.edges:
        parts.setdefault(find(id(e.v0)), ([], []))[1].append(e)
    return sorted(parts.values(), key=lambda p: (-len(p[0]), -len(p[1])))


def copy_part(faces, edges) -> Mesh:
    """A new mesh holding a deep copy of ``faces`` and ``edges`` — attrs,
    holes and every edge flag included — in one vectorized weld, the recipe
    :func:`core.group.transformed_mesh` uses (a part of a leafy import is
    thousands of faces, and a per-face walk froze the UI at that scale)."""
    import numpy as np
    from core.topology import _maximal_holes

    new = Mesh()
    flat: list = []
    for e in edges:
        flat.append((e.a.x(), e.a.y(), e.a.z()))
        flat.append((e.b.x(), e.b.y(), e.b.z()))
    n_edge_pts = len(flat)
    ring_sizes: list = []
    ring_counts: list = []
    attrs_list: list = []
    for f in faces:
        holes = f.holes or []
        if len(holes) > 1:
            holes = _maximal_holes([list(h) for h in holes])
        ring_counts.append(1 + len(holes))
        ring_sizes.append(len(f.vertices))
        flat.extend((v.x(), v.y(), v.z()) for v in f.vertices)
        for h in holes:
            ring_sizes.append(len(h))
            flat.extend((v.x(), v.y(), v.z()) for v in h)
        attrs_list.append(dict(f.attrs) if f.attrs else None)
    if not flat:
        return new
    vobjs, inverse = new.bulk_weld(np.array(flat, dtype=np.float64))
    emap = None
    if edges:
        ia = inverse[0:n_edge_pts:2]
        ib = inverse[1:n_edge_pts:2]
        emap = new.add_edges_welded(
            vobjs, ia, ib, [(e.soft, e.curve, e.layer) for e in edges])
        # ``add_edges_welded`` carries three of the flags; stamp them all,
        # so a hidden edge stays hidden (see core.mesh.EDGE_FLAG_NAMES).
        u = len(vobjs)
        for e, a, b in zip(edges, ia.tolist(), ib.tolist()):
            ne = emap.get(a * u + b if a <= b else b * u + a)
            if ne is not None:
                stamp_edge_flags(ne, edge_flags(e))
    if ring_counts:
        new.add_faces_welded(vobjs, inverse[n_edge_pts:], ring_sizes,
                             ring_counts, attrs_list, edge_map=emap)
    new.resplit_curves()
    return new


def split_into_pieces(group) -> list:
    """The pieces ``group`` comes apart into, as new groups in the group's
    own coordinates (identity placements, ready to :meth:`Group.adopt`), or
    ``[]`` when there is nothing to split — one piece and no children, which
    is exactly what the group already is.

    Everything the group holds is read together, its own mesh and every
    nested placement through its matrix, so fragments the file kept apart
    (a seat in three materials) join into the one piece they are. The group
    itself is never touched; the caller swaps the result in through a
    command, which is what makes the split undoable."""
    from PySide6.QtGui import QMatrix4x4
    from core.group import Group, world_mesh
    from core.i18n import tr

    # Read the contents in the group's frame, not the world's: the pieces
    # live inside it, and its own matrix keeps placing them.
    frame = Group(group.mesh)
    frame.children = list(group.children)
    local = world_mesh(frame)
    parts = connected_parts(local)
    if len(parts) <= 1 and not group.children:
        return []
    kids = group.children
    if (not group.mesh.faces and len(parts) == len(kids)
            and all(not k.children and len(connected_parts(k.mesh)) == 1
                    for k in kids)):
        return []                  # already split: one piece per child
    pieces = []
    for n, (faces, edges) in enumerate(parts, start=1):
        piece = Group(copy_part(faces, edges), name=tr("Piece {n}", n=n))
        piece.xform = QMatrix4x4()
        pieces.append(piece)
    return pieces
