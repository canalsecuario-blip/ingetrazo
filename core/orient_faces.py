# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""SketchUp's Orient Faces: make every face connected to a chosen face wind
the same way it does (issue #77, @pacaeiro).

Two faces sharing an edge agree when they walk that edge in OPPOSITE
directions — that is what makes their fronts face the same side of the
surface. So the chosen face is the reference and the agreement spreads edge
by edge through the connected faces, the way SketchUp's does. Unlike
:func:`core.orient.orient_outward`, it does not ask which side is outside:
the user says so by choosing the face, which also works on open surfaces
(a terrain, a roof sheet) where "outside" has no meaning.

It crosses only edges shared by exactly TWO faces. Where three or more meet
(a wall between two rooms) there is no single neighbour to agree with, and
SketchUp stops there too.
"""
from __future__ import annotations

from collections import deque


def _directed_edges(face, flipped: bool):
    """Each boundary step of ``face`` as a ``(from, to)`` vertex pair, in the
    order the face walks it — reversed when the face is to be flipped."""
    for loop in [face.loop, *(getattr(face, "hole_loops", None) or ())]:
        n = len(loop)
        for i in range(n):
            a, b = loop[i], loop[(i + 1) % n]
            yield (b, a) if flipped else (a, b)


def _edge_between(a, b):
    for e in a.edges:
        if (e.v0 is a and e.v1 is b) or (e.v0 is b and e.v1 is a):
            return e
    return None


def _walks(face, a, b) -> bool:
    """Does ``face`` (as it is wound now) walk the step ``a → b``?"""
    return any(x is a and y is b for x, y in _directed_edges(face, False))


def faces_to_flip(seed) -> list:
    """The faces connected to ``seed`` that must be reversed so they all
    wind like it. ``seed`` itself is never in the list."""
    flip = {id(seed): False}
    faces = {id(seed): seed}
    todo = deque([seed])
    while todo:
        face = todo.popleft()
        for a, b in _directed_edges(face, flip[id(face)]):
            edge = _edge_between(a, b)
            if edge is None or len(edge.faces) != 2:
                continue
            other = next((f for f in edge.faces if f is not face), None)
            if other is None or id(other) in flip:
                continue
            # Agreement = the neighbour walks this edge the other way, b → a.
            flip[id(other)] = _walks(other, a, b)
            faces[id(other)] = other
            todo.append(other)
    return [faces[k] for k, f in flip.items() if f]


def connected_count(seed) -> int:
    """How many faces the orientation reached, ``seed`` included."""
    seen = {id(seed)}
    todo = deque([seed])
    while todo:
        face = todo.popleft()
        for a, b in _directed_edges(face, False):
            edge = _edge_between(a, b)
            if edge is None or len(edge.faces) != 2:
                continue
            for other in edge.faces:
                if id(other) not in seen:
                    seen.add(id(other))
                    todo.append(other)
    return len(seen)
