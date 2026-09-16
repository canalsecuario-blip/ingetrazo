# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""One status-bar hint at a time, for the tool and the step it is in —
SketchUp's status bar («Select objects. Shift = Add/Subtract…»), not a
strip of every shortcut at once (Marco, 2026-09-15: «mostrarlos varios al
mismo tiempo como que no es bueno»).

:func:`hint_for` answers for a tool key and its live state. Phases are
read off the tool: ``start_point`` set means the first click is down;
the arc knows its bulge step, the fillet its sizing step. Tools not in
the table fall back to their name."""
from __future__ import annotations

from core.i18n import tr

#: Tool key → hint per phase. A plain string is the same hint always.
HINTS: dict = {
    "select": "Select objects. Shift = add/remove, Ctrl = add. Double-click a group to edit it.",
    "eraser": "Drag over edges to erase them. Shift = hide instead.",
    "paint": "Click a face to paint it. Alt = sample the material under the cursor.",
    "line": ("Click the start point. Arrows lock an axis, Shift locks the inference.",
             "Click the end point, or type the length and Enter. Arrows lock an axis."),
    "freehand": "Press and drag to draw a freehand line.",
    "rectangle": ("Click the first corner. Arrows pick the plane.",
                  "Click the opposite corner, or type width;height and Enter."),
    "rotated_rect": ("Click the first corner of the base edge.",
                     "Click the end of the base edge, then the height; or type it."),
    "circle": ("Click the centre. Arrows pick the plane; Down over an edge makes it perpendicular to the edge. Type the number of sides and Enter first, if you want.",
               "Click the radius, or type it and Enter."),
    "polygon": ("Click the centre. Arrows pick the plane; Down over an edge makes it perpendicular to the edge. Type the number of sides and Enter first, if you want.",
                "Click the radius, or type it and Enter."),
    "arc": {
        "idle": "Click the start point — on an edge to draw a tangent arc.",
        "end": "Click the end point. Magenta on the next edge = same distance: double-click to round.",
        "bulge": "Click the bulge, or type it. 'Nr' = radius, 'Ns' = segments. Alt keeps the corner.",
    },
    "arc3": ("Click the start point.", "Click a point the arc passes through, then the end."),
    "center_arc": ("Click the centre.", "Click the start of the arc, then its end; or type the angle."),
    "pie": ("Click the centre.", "Click the start of the wedge, then its end; or type the angle."),
    "pushpull": ("Click a face and move. Ctrl keeps the starting face.",
                 "Move, or type the distance and Enter. Double-click repeats the last."),
    "move": ("Click what to move (or select it first). Arrows lock an axis.",
             "Click the destination, or type the distance and Enter. Arrows lock an axis."),
    "rotate": ("Click the centre of rotation — on a face, the protractor takes its plane.",
               "Click the start of the angle, then the end; or type the degrees."),
    "scale": ("Select something, then drag a grip: corners uniform, edges along an axis.",
              "Drag, or type a factor (2) or a size (2m). Ctrl = about centre, Shift = uniform."),
    "flip": "Click the plane to mirror the selection across.",
    "followme": ("Select the path, then click the profile face. Alt = sweep along the selection.",
                 "Move along the path; click to finish."),
    "offset": ("Click a face, or connected edges, to offset.",
               "Move to set the offset, or type it and Enter."),
    "fillet": {
        "idle": "Click an edge to round it (or select edges first); type the radius and Enter.",
        "sizing": "Move to set the radius, or type it and Enter; click to round. 'Ns' = segments.",
    },
    "tape": ("Click a point to measure, or an edge to pull a guide. Arrows lock an axis.",
             "Click the second point, or type the distance and Enter for an exact guide."),
    "protractor": ("Click the vertex of the angle.",
                   "Click the start of the angle, then the end; or type the degrees for a guide."),
    "dimension": ("Click the first point of the dimension.",
                  "Click the second point, then place the dimension line."),
    "text": "Click a point to attach a label; click empty space for a screen note.",
    "geopath": "Click the points of the path; Enter or double-click finishes.",
    "section": "Click a face to place the section plane on it. Shift keeps the orientation.",
    "texture_position": "Drag the texture or a pin: red moves, green scales/rotates, blue shears. Enter finishes.",
    "image": "Click the first corner of the image, then the opposite one. Shift frees the aspect.",
    "paste": "Click where the copy goes. Arrows lock an axis.",
    "place_group": "Click where the component goes.",
}

NAV_HINTS: dict = {
    "orbit": "Drag to orbit. Shift = pan. Wheel = zoom. The middle button orbits from any tool.",
    "pan": "Drag to pan. Wheel = zoom.",
    "zoom": "Drag up to zoom in, down to zoom out. Wheel zooms at the cursor.",
    "zoom_window": "Drag a box to zoom into it.",
}


def phase_of(key: str, tool) -> str:
    """Which step the tool is in: ``idle``, ``started``, or a tool-specific
    phase (the arc's ``end`` / ``bulge``, the fillet's ``sizing``)."""
    if key == "arc":
        if getattr(tool, "end_point", None) is not None:
            return "bulge"
        return "end" if getattr(tool, "start_point", None) is not None else "idle"
    if key == "fillet":
        return "sizing" if getattr(tool, "sizing", False) else "idle"
    if getattr(tool, "start_point", None) is not None:
        return "started"
    if getattr(tool, "dragging", False) or getattr(tool, "nodes", None):
        return "started"
    return "idle"


def hint_for(key: str | None, tool, nav_mode: str | None = None) -> str:
    """The one line the status bar shows now."""
    if nav_mode is not None and nav_mode in NAV_HINTS:
        return tr(NAV_HINTS[nav_mode])
    entry = HINTS.get(key or "")
    if entry is None:
        name = getattr(tool, "name", None)
        return tr("{name}: Esc cancels.", name=tr(name)) if name else ""
    if isinstance(entry, str):
        return tr(entry)
    phase = phase_of(key, tool)
    if isinstance(entry, dict):
        return tr(entry.get(phase) or entry.get("idle") or "")
    idle, started = entry
    return tr(started if phase != "idle" else idle)
