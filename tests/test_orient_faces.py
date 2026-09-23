"""Orient Faces (issue #77): the faces connected to the chosen one wind
like it, as SketchUp's Orient Faces does."""
from __future__ import annotations

from PySide6.QtGui import QVector3D as V

from core.history import FlipFacesCommand
from core.mesh import Mesh
from core.orient_faces import connected_count, faces_to_flip


def _normal(face):
    p = [v.position for v in face.loop]
    n = V()
    for i in range(len(p)):
        a, b = p[i], p[(i + 1) % len(p)]
        n += V((a.y() - b.y()) * (a.z() + b.z()),
               (a.z() - b.z()) * (a.x() + b.x()),
               (a.x() - b.x()) * (a.y() + b.y()))
    return n.normalized()


def _agree(mesh) -> bool:
    """Every edge shared by two faces is walked in opposite directions."""
    for e in mesh.edges:
        if len(e.faces) != 2:
            continue
        dirs = []
        for f in e.faces:
            loop = f.loop
            for i in range(len(loop)):
                a, b = loop[i], loop[(i + 1) % len(loop)]
                if {a, b} == {e.v0, e.v1}:
                    dirs.append((a, b))
        if dirs[0] == dirs[1]:
            return False
    return True


def _cube(scrambled=True):
    """A unit cube; with ``scrambled`` three of its faces wind inward."""
    m = Mesh()
    c = [V(x, y, z) for z in (0, 1) for y in (0, 1) for x in (0, 1)]
    quads = {
        "bottom": [0, 2, 3, 1], "top": [4, 5, 7, 6],
        "front": [0, 1, 5, 4], "back": [2, 6, 7, 3],
        "left": [0, 4, 6, 2], "right": [1, 3, 7, 5],
    }
    faces = {}
    for name, q in quads.items():
        if scrambled and name in ("top", "left", "back"):
            q = list(reversed(q))
        faces[name] = m.add_face([c[i] for i in q])
    return m, faces


def test_a_scrambled_cube_winds_like_the_chosen_face():
    m, faces = _cube()
    seed = faces["bottom"]
    before = _normal(seed)
    flip = faces_to_flip(seed)
    assert {id(f) for f in flip} == {id(faces[k]) for k in ("top", "left", "back")}
    FlipFacesCommand(flip).do(_Scene(m))
    assert _agree(m)
    assert _normal(seed) == before           # the chosen face never turns
    # Bottom faced down (outward), so every face now faces out.
    assert _normal(faces["top"]).z() > 0.99
    assert _normal(faces["left"]).x() < -0.99


def test_choosing_an_inward_face_turns_the_whole_cube_inward():
    m, faces = _cube(scrambled=False)
    FlipFacesCommand([faces["front"]]).do(_Scene(m))   # front now inward
    FlipFacesCommand(faces_to_flip(faces["front"])).do(_Scene(m))
    assert _agree(m)
    assert _normal(faces["top"]).z() < -0.99


def test_an_already_consistent_surface_needs_nothing():
    m, faces = _cube(scrambled=False)
    assert faces_to_flip(faces["top"]) == []
    assert connected_count(faces["top"]) == 6


def test_an_open_surface_follows_the_chosen_face():
    m = Mesh()
    a = m.add_face([V(0, 0, 0), V(1, 0, 0), V(1, 1, 0), V(0, 1, 0)])
    b = m.add_face([V(1, 0, 0), V(1, 1, 0), V(2, 1, 0), V(2, 0, 0)])  # down
    assert faces_to_flip(a) == [b]
    assert faces_to_flip(b) == [a]


def test_it_stops_where_three_faces_meet_an_edge():
    m = Mesh()
    a = m.add_face([V(0, 0, 0), V(1, 0, 0), V(1, 1, 0), V(0, 1, 0)])
    m.add_face([V(1, 0, 0), V(1, 1, 0), V(2, 1, 0), V(2, 0, 0)])
    m.add_face([V(1, 0, 0), V(1, 1, 0), V(1, 1, 1), V(1, 0, 1)])
    assert faces_to_flip(a) == []
    assert connected_count(a) == 1


class _Scene:
    """What FlipFacesCommand touches of a scene."""

    def __init__(self, mesh):
        self.mesh = mesh
        self.groups = []
        self.version = 0
