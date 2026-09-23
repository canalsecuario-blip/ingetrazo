# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""Solid booleans on groups and components — SketchUp's Solid Tools.

Outer Shell, Union, Subtract, Trim, Intersect and Split, with SketchUp's
rules (help.sketchup.com, «Modeling Complex 3D Shapes with Solid Tools»):

* A **solid** is a group or component instance with a closed volume: every
  edge borders exactly two faces, no stray edges, no groups nested inside.
* The result is always a **group** (a component instance used as input is
  replaced by a group; its definition and other instances do not change).
* Every face keeps the material it had; the faces a cut creates take the
  material of the solid that cut them. A container's paint is baked onto
  the faces that wore it.
* Subtract: the FIRST solid cuts the SECOND and disappears. Trim: the same,
  the cutter stays. Split: A−B, B−A and A∩B, three groups. Outer Shell:
  the union without anything inside (inner voids go too); Union keeps them.

Deviation, on purpose: the result goes on the layer of the solid that
receives the operation, not on the current layer (a SketchUp habit its own
users complain about).

The arithmetic is manifold3d (Apache-2.0, the kernel of OpenSCAD and
Blender's booleans): robust on the coincident faces and shared edges real
models are full of. Each triangle carries the id of the face it came from,
which is how materials survive; the result's triangles are merged back into
clean polygons with holes by ``formats.fuse`` (coplanar, same material), and
the seams of curved surfaces stay soft.
"""
from __future__ import annotations

import numpy as np
from PySide6.QtGui import QVector3D

from core.group import Group, world_mesh
from core.mesh import Mesh

#: Operations, in SketchUp's help order.
OUTER_SHELL, UNION, SUBTRACT, TRIM, INTERSECT, SPLIT = (
    "outer_shell", "union", "subtract", "trim", "intersect", "split")
OPS = (OUTER_SHELL, UNION, SUBTRACT, TRIM, INTERSECT, SPLIT)

#: The group names SketchUp gives its results (translated where shown).
RESULT_NAMES = {OUTER_SHELL: "Outer shell", UNION: "Union",
                SUBTRACT: "Difference", TRIM: "Trimmed",
                INTERSECT: "Intersection", SPLIT: "Split"}


class SolidError(Exception):
    """An operation that cannot run; the message is for the user."""


# ---- What is a solid ---------------------------------------------------------

def solid_report(mesh) -> tuple[bool, float | None]:
    """``(is_solid, volume)`` for a mesh: every edge between exactly two
    faces, no stray edges, at least one face. Volume in m³ when solid."""
    if not mesh.faces:
        return False, None
    for e in mesh.edges:
        n = sum(1 for f in e.faces if not getattr(f, "interior", False))
        if n != 2:
            return False, None
    from core.bim import face_set_volume
    vol = face_set_volume([f for f in mesh.faces
                           if not getattr(f, "interior", False)])
    if vol is None or vol <= 1e-12:
        return False, None
    return True, vol


def is_solid(group) -> bool:
    return solid_volume(group) is not None


def solid_volume(group) -> float | None:
    """The group's volume when it is a solid (SketchUp's «Solid Group»),
    else ``None``. Nested groups disqualify it, as in SketchUp."""
    if not isinstance(group, Group) or getattr(group, "children", None):
        return None
    ok, vol = solid_report(world_mesh(group))
    return vol if ok else None


# ---- Group <-> manifold --------------------------------------------------------

class _Sources:
    """Every source face, globally numbered across the inputs: what a
    result triangle's ``face_id`` points back to."""

    def __init__(self) -> None:
        self.attrs: list[dict] = []
        #: Pairs of source face ids joined by a soft edge (curved surfaces).
        self.soft_pairs: set[tuple[int, int]] = set()


def _to_manifold(group, sources: _Sources):
    import manifold3d as m3d
    from core.materials import effective_attrs
    from core.group import effective_material
    mesh = world_mesh(group)
    paint = effective_material(group)
    index: dict = {}
    verts: list = []
    tris: list = []
    fids: list = []
    face_id: dict = {}

    def vid(p: QVector3D) -> int:
        k = (p.x(), p.y(), p.z())
        i = index.get(k)
        if i is None:
            i = index[k] = len(verts)
            verts.append(k)
        return i

    for f in mesh.faces:
        if getattr(f, "interior", False):
            continue
        fid = len(sources.attrs)
        face_id[id(f)] = fid
        attrs = effective_attrs(dict(f.attrs or {}), paint)
        sources.attrs.append({k: (dict(v) if isinstance(v, dict) else v)
                              for k, v in attrs.items()})
        n = f.normal()
        for a, b, c in f.triangulate(n):
            tris.append((vid(a), vid(b), vid(c)))
            fids.append(fid)
    for e in mesh.edges:
        if getattr(e, "soft", False):
            fs = [face_id.get(id(f)) for f in e.faces]
            fs = [x for x in fs if x is not None]
            if len(fs) == 2:
                sources.soft_pairs.add((min(fs), max(fs)))
    if not tris:
        raise SolidError("empty")
    v = np.asarray(verts, dtype=np.float64)
    t = np.asarray(tris, dtype=np.uint32)
    # Outward orientation: a negative signed volume means the faces point in.
    a, b, c = v[t[:, 0]], v[t[:, 1]], v[t[:, 2]]
    if np.einsum("ij,ij->i", a, np.cross(b, c)).sum() < 0:
        t = t[:, ::-1].copy()
    man = m3d.Manifold(m3d.Mesh64(vert_properties=v, tri_verts=t,
                                  face_id=np.asarray(fids, dtype=np.uint32)))
    if man.status() != m3d.Error.NoError:
        raise SolidError("not manifold")
    return man


def _loops_from(man, sources: _Sources, drop_voids: bool = False):
    """The result's triangles as ``(pts, attrs, fid)`` loops, optionally
    without the inner shells (Outer Shell)."""
    mesh = man.to_mesh64()
    v = np.asarray(mesh.vert_properties, dtype=np.float64)[:, :3]
    t = np.asarray(mesh.tri_verts, dtype=np.int64)
    fid = np.asarray(mesh.face_id, dtype=np.int64)
    if len(t) == 0:
        return []
    keep = np.ones(len(t), dtype=bool)
    if drop_voids:
        keep = _outer_shell_mask(v, t)
    loops = []
    for (i, j, k), f, ok in zip(t.tolist(), fid.tolist(), keep.tolist()):
        if not ok:
            continue
        pts = [QVector3D(*v[i]), QVector3D(*v[j]), QVector3D(*v[k])]
        attrs = sources.attrs[f] if 0 <= f < len(sources.attrs) else {}
        loops.append((pts, attrs, f))
    return loops


def _outer_shell_mask(v, t):
    """Keep the triangles of the shells that bound volume from outside:
    an inner void is a connected shell of negative signed volume."""
    n = len(t)
    parent = list(range(len(v)))

    def find(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    for a, b, c in t.tolist():
        ra, rb, rc = find(a), find(b), find(c)
        parent[rb] = ra
        parent[find(rc)] = ra
    roots = np.array([find(a) for a in t[:, 0].tolist()])
    a, b, c = v[t[:, 0]], v[t[:, 1]], v[t[:, 2]]
    vol = np.einsum("ij,ij->i", a, np.cross(b, c))
    keep = np.ones(n, dtype=bool)
    for r in set(roots.tolist()):
        sel = roots == r
        if vol[sel].sum() < 0:
            keep[sel] = False
    return keep


def _group_from_loops(loops, sources: _Sources, name: str, layer):
    """A new group with clean polygon faces: coplanar same-material
    triangles merged (formats.fuse), collinear corners dropped, and the
    seams between faces that came from a soft pair kept soft."""
    from formats.fuse import fuse_coplanar_loops
    tagged = []
    for pts, attrs, f in loops:
        a = dict(attrs)
        a["_solid_src"] = f            # travels through the fuse, then goes
        tagged.append((pts, a))
    fused = fuse_coplanar_loops(tagged)
    mesh = Mesh()
    polys = []
    for outer, holes, attrs, originals in fused:
        polys.append((list(outer), [list(h) for h in (holes or [])],
                      attrs, originals))
    _drop_collinear(polys)
    face_src: dict = {}
    for outer, holes, attrs, originals in polys:
        clean = dict(attrs or {})
        src = clean.pop("_solid_src", None)
        try:
            face = mesh.add_face(outer, holes or None)
            made = [face]
        except Exception:  # noqa: BLE001 — fall back to the source loops
            made = []
            for pts in originals:
                try:
                    made.append(mesh.add_face(pts))
                except Exception:  # noqa: BLE001
                    pass
        for face in made:
            face.attrs.update(clean)
            face_src[id(face)] = src
    for e in mesh.edges:
        fs = [face_src.get(id(f)) for f in e.faces]
        if len(fs) == 2 and None not in fs:
            if (min(fs), max(fs)) in sources.soft_pairs:
                e.soft = True
    g = Group(mesh, name=name)
    if layer is not None:
        g.layer = layer
    return g


def _drop_collinear(polys, tol: float = 1e-9) -> None:
    """A corner every ring passes straight through is not a corner: the
    triangulation left them along edges, and SketchUp's result has none."""
    def key(p):
        return (round(p.x(), 7), round(p.y(), 7), round(p.z(), 7))

    rings = []
    for outer, holes, _a, _o in polys:
        rings.append(outer)
        rings.extend(holes or [])
    straight: dict = {}
    for ring in rings:
        n = len(ring)
        for i in range(n):
            p0, p1, p2 = ring[i - 1], ring[i], ring[(i + 1) % n]
            d1, d2 = p1 - p0, p2 - p1
            ok = (QVector3D.crossProduct(d1, d2).length()
                  <= tol * max(d1.length() * d2.length(), 1e-12) * 1e3
                  and QVector3D.dotProduct(d1, d2) > 0)
            k = key(p1)
            straight[k] = straight.get(k, True) and ok
    drop = {k for k, v in straight.items() if v}
    if not drop:
        return
    for ring in rings:
        if len(ring) - sum(1 for p in ring if key(p) in drop) >= 3:
            ring[:] = [p for p in ring if key(p) not in drop]


# ---- The operations ------------------------------------------------------------

def _need_solid(g) -> None:
    if not is_solid(g):
        raise SolidError("not a solid")


def run(op: str, groups: list) -> tuple[list, list]:
    """Run ``op`` on ``groups`` (in pick order: for Subtract and Trim the
    first is the cutter, the second the target). Returns
    ``(removed, created)`` — the groups to take out of the model and the
    new result groups, in the order they should appear."""
    import manifold3d as m3d
    if op not in OPS:
        raise ValueError(op)
    if len(groups) < 2:
        raise SolidError("two solids")
    for g in groups:
        _need_solid(g)
    sources = _Sources()
    mans = [_to_manifold(g, sources) for g in groups]
    first, second = groups[0], groups[1]
    from core.i18n import tr
    name = tr(RESULT_NAMES[op])

    def out(man, label, layer, drop_voids=False):
        loops = _loops_from(man, sources, drop_voids)
        if not loops:
            return None
        return _group_from_loops(loops, sources, label, layer)

    target_layer = getattr(second if op in (SUBTRACT, TRIM) else first,
                           "layer", None)
    if op in (UNION, OUTER_SHELL):
        man = m3d.Manifold.batch_boolean(mans, m3d.OpType.Add)
        res = out(man, name, target_layer, drop_voids=(op == OUTER_SHELL))
        if res is None:
            raise SolidError("empty")
        return list(groups), [res]
    if op == INTERSECT:
        man = m3d.Manifold.batch_boolean(mans, m3d.OpType.Intersect)
        res = out(man, name, target_layer)
        if res is None:
            raise SolidError("no overlap")
        return list(groups), [res]
    a, b = mans[0], mans[1]
    if (a ^ b).is_empty():
        raise SolidError("no overlap")
    if op in (SUBTRACT, TRIM):
        res = out(b - a, name, target_layer)
        if res is None:
            raise SolidError("empty")
        removed = [first, second] if op == SUBTRACT else [second]
        return removed, [res]
    # SPLIT: B−A, A−B, A∩B — three groups.
    made = [out(b - a, name, getattr(second, "layer", None)),
            out(a - b, name, getattr(first, "layer", None)),
            out(a ^ b, name, getattr(first, "layer", None))]
    return [first, second], [g for g in made if g is not None]


# ---- Undoable command ----------------------------------------------------------

from core.history import Command  # noqa: E402  (history imports group, not us)


class SolidOperationCommand(Command):
    """One solid operation as one undo step: the inputs leave the list they
    live in (the model, or the container being edited), the results take
    the place of the first input that left, and they end up selected."""

    def __init__(self, op: str, groups: list) -> None:
        self.op = op
        self.groups = list(groups)
        self.removed: list | None = None
        self.created: list | None = None
        self._slots: list = []            # (owner list, index, group)
        self._home = None
        self._selection = None

    def prepare(self) -> None:
        """Run the boolean now, so a :class:`SolidError` reaches the caller
        (``History.execute`` swallows what ``do`` raises)."""
        if self.created is None:
            self.removed, self.created = run(self.op, self.groups)

    def do(self, scene) -> None:
        from core.history import group_owner_list
        self.prepare()                     # once; redo reuses the result
        self._selection = set(scene.selection)
        home = group_owner_list(scene, self.groups[-1 if self.op in (
            SUBTRACT, TRIM) else 0]) or scene.groups
        self._home = home
        self._slots = []
        for g in self.removed:
            owner = group_owner_list(scene, g)
            if owner is None:
                continue
            i = owner.index(g)
            self._slots.append((owner, i, g))
        at = min((i for o, i, _g in self._slots if o is home),
                 default=len(home))
        for owner, _i, g in self._slots:
            owner.remove(g)
            scene.selection.discard(g)
        home[at:at] = self.created
        scene.selection = set(self.created)
        scene.version += 1

    def undo(self, scene) -> None:
        for g in self.created or []:
            if g in self._home:
                self._home.remove(g)
        for owner, i, g in sorted(self._slots, key=lambda s: s[1]):
            owner.insert(min(i, len(owner)), g)
        scene.selection = set(self._selection or ())
        scene.version += 1
