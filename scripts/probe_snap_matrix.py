#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""Freeze what the snap engine answers today, so a change has to prove it
did not move anything it was not meant to move.

The safety net for issue #31's second part (see
``~/Proyectos/ingetrazo/inferencia-pantalla/plan.md``). The inference runs
on every mouse move and decides where every click lands; months of tuning
sit in it — the sticky acquired edge, the origin beating the axis line, the
arrow locks, the hover plane, excluding the geometry being dragged. A
careless change there does not fail a test, it makes drawing *feel* wrong,
and by then it is too late to measure.

So: walk a grid of camera × cursor × tool × Alt state × scene, ask the
REAL path (``Viewport._refresh_snap``, not ``compute_snap`` in a vacuum, so
the work plane, the neighbourhood and the lock-line projection are all in
play), and write one line per cell. Record it on main, change something,
run it again, diff. Cells that moved and should not have are the bug.

    scripts/probe_snap_matrix.py -o base.jsonl
    # …change something…
    scripts/probe_snap_matrix.py -o after.jsonl
    diff <(sort base.jsonl) <(sort after.jsonl)

It must reproduce itself byte for byte on two consecutive runs, or it is
not a baseline. ``--selftest`` checks exactly that.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import pathlib
import sys

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from PySide6.QtCore import QPointF                         # noqa: E402
from PySide6.QtGui import QVector3D                        # noqa: E402
from PySide6.QtWidgets import QApplication                 # noqa: E402

#: Every standard view plus four obliques. The obliques matter: pacaeiro's
#: report is about "certain viewport positions", and a bug that only shows
#: at an angle hides perfectly in the seven presets.
CAMERAS = [
    ("top", None), ("bottom", None), ("front", None), ("back", None),
    ("left", None), ("right", None), ("iso", None),
    ("obl-a", (-30.0, 12.0)), ("obl-b", (-75.0, 55.0)),
    ("obl-c", (20.0, -20.0)), ("obl-d", (160.0, 70.0)),
]

#: With nothing around, and with a corner to compete against — the named
#: point snaps must keep beating the axis, and only the second scene can
#: show it.
#: The third, "midline", was added 2026-09-18 and is the one that matters
#: most: a 4 m edge whose LEFT END is the acquired point, so its midpoint
#: lies on that point's own alignment line. That is Marco's case, and until
#: this scene existed the grid could not express it — it reported zero
#: changes for a fix whose effect had just been measured by hand twice.
#: A net proves nothing about a shape it cannot hold.
#: The fourth, "walls", was added 2026-09-19 for Rafael's window (02:20 of
#: his second review): a corner encouraged on ONE wall and the cursor on
#: ANOTHER — perpendicular or opposite — at that corner's height. Every
#: earlier scene was flat, so no cell of any earlier baseline ever had a
#: vertical face under the cursor with a reference on a different plane.
SCENES = ("empty", "corner", "midline", "walls")

TOOLS = ("line", "rectangle", "circle", "arc", "move", "pushpull")

ALT_MODES = ("all", "off", "parallel_perp")

#: Screen-space ring around the start point. Directions, not world
#: offsets: the cursor is a pixel and that is where the question lives.
#:
#: 170 px was added 2026-09-18, after the grid reported ZERO changes for a
#: fix whose effect had just been measured by hand. The ring is centred on
#: the start point at the origin and the competing geometry sits 1.5 m out,
#: which at this camera is ~90 px: the cursor barely reached it, so an
#: acquired-point alignment and a midpoint never actually competed. Third
#: time this net has had to be widened — it proves nothing it cannot reach.
RADII_PX = (30.0, 90.0, 170.0)

#: With and without a point the user has hovered and left. Added 2026-09-18:
#: the grid cleared it on every cell, so it measured nothing about the
#: acquired-point rules — and those are exactly what Marco's rectangle needs
#: («en la segunda esquina está la referencia pero al momento de jalar el
#: rectángulo se pierde la referencia»). A baseline that cannot see a rule
#: cannot protect it.
#: The third, 2026-09-19, sits 1.2 m up on the "walls" scene's front wall:
#: an acquired point OFF the plane the cursor is on, which the point on
#: the ground could never be.
ACQUIRED = (None, (2.0, 1.0, 0.0), (0.5, -1.5, 1.2))

#: Before the first click, and with an operation under way. Added
#: 2026-09-18 and the biggest hole of the four: ``_reset_tool`` always gave
#: the tool a start point, so every cell of every earlier baseline measured
#: the SECOND half of a gesture. Marco's midpoint bug lives in the first
#: click, and the grid reported zero changes for its fix three times
#: running while a hand measurement showed 0.65 cm moving to 0.00.
STARTED = (True, False)


def _round(v: float) -> float:
    """Six decimals: enough to catch a real move, coarse enough that the
    last float32 bit does not make two identical runs differ."""
    return round(float(v), 6)


def _build_scene(vp, kind: str) -> None:
    from core.scene import Scene
    vp.scene = Scene()
    if kind == "midline":
        # Runs through ACQUIRED, so the alignment line from it lies along
        # the edge and its midpoint sits on that line — the two compete.
        m = vp.scene.mesh
        m.add_edge(QVector3D(2.0, 1.0, 0.0), QVector3D(6.0, 1.0, 0.0))
    if kind == "corner":
        # A unit square whose corner sits 1.5 m along +X from the start
        # point, close enough that its endpoint and midpoint compete.
        m = vp.scene.mesh
        m.add_face([QVector3D(1.5, 0.0, 0.0), QVector3D(2.5, 0.0, 0.0),
                    QVector3D(2.5, 1.0, 0.0), QVector3D(1.5, 1.0, 0.0)])
    if kind == "walls":
        # Three walls of a 3 x 3 room around the start point, 3 m high, on
        # a slab, open at the back and above so the cameras see inside:
        # the front wall (y = -1.5) carries the third ACQUIRED point, the
        # right wall (x = 1.5) is perpendicular to it and the far wall
        # (y = 1.5) faces it. The cursor ring reaches all three.
        m = vp.scene.mesh
        P = QVector3D
        m.add_face([P(-1.5, -1.5, 0.0), P(1.5, -1.5, 0.0),
                    P(1.5, 1.5, 0.0), P(-1.5, 1.5, 0.0)])
        m.add_face([P(-1.5, -1.5, 0.0), P(1.5, -1.5, 0.0),
                    P(1.5, -1.5, 3.0), P(-1.5, -1.5, 3.0)])
        m.add_face([P(1.5, -1.5, 0.0), P(1.5, 1.5, 0.0),
                    P(1.5, 1.5, 3.0), P(1.5, -1.5, 3.0)])
        m.add_face([P(1.5, 1.5, 0.0), P(-1.5, 1.5, 0.0),
                    P(-1.5, 1.5, 3.0), P(1.5, 1.5, 3.0)])
    vp.scene.version += 1


def _reset_tool(vp, start: QVector3D | None) -> object | None:
    """Put the tool in a known state. Anything that remembers the previous
    sample — a dwell point, an acquired edge, a work plane — would make the
    grid order-dependent, and an order-dependent baseline is worthless."""
    tool = vp.active_tool
    if tool is None:
        return None
    for attr, value in (("start_point", start), ("work_plane", None),
                        ("chain_first_point", start), ("plane_lock", None)):
        if hasattr(tool, attr):
            try:
                setattr(tool, attr, value)
            except AttributeError:      # a read-only property
                pass
    vp._acquired_edge = None
    vp._acquired_point = None
    vp._acquired_face_normal = None
    vp._encouraged = []
    vp._dwell_point = None
    vp._shift_lock = None
    vp.axis_lock = None
    vp.reference_edge = None
    vp.reference_mode = None
    return tool


def run(out_path: str, radii=RADII_PX, directions: int = 16,
        cameras=CAMERAS, tools=TOOLS, scenes=SCENES,
        alt_modes=ALT_MODES, acquired=ACQUIRED, started=STARTED) -> int:
    app = QApplication.instance() or QApplication([])
    from views.main_window import MainWindow

    win = MainWindow()
    win.show()
    win.resize(1200, 800)
    app.processEvents()
    vp = win.viewport
    start_world = QVector3D(0.0, 0.0, 0.0)
    rows = 0
    with open(out_path, "w", encoding="utf-8") as fh:
        for scene_kind in scenes:
            _build_scene(vp, scene_kind)
            for cam_name, oblique in cameras:
                if oblique is None:
                    vp.camera.set_view(cam_name)
                else:
                    vp.camera.yaw = math.radians(oblique[0])
                    vp.camera.pitch = math.radians(oblique[1])
                vp.camera.distance = 20.0
                vp.camera.target = QVector3D(0.0, 0.0, 0.0)
                app.processEvents()
                sx, sy = vp._world_to_pixel(start_world)
                for tool_key in tools:
                    try:
                        win._activate_tool(tool_key)
                    except Exception:           # noqa: BLE001
                        continue
                    if vp.active_tool is None:
                        continue
                    for empezado in started:
                        for acq in acquired:
                          for mode in alt_modes:
                              for radius in radii:
                                  for i in range(directions):
                                      ang = 2.0 * math.pi * i / directions
                                      px = sx + radius * math.cos(ang)
                                      py = sy + radius * math.sin(ang)
                                      _reset_tool(vp, start_world if empezado else None)
                                      # After the reset, never before: the reset
                                      # is what clears it.
                                      if acq is not None:
                                          vp._acquired_point = QVector3D(*acq)
                                          vp._encouraged = [QVector3D(*acq)]
                                      vp.linear_inference_mode = mode
                                      vp._last_mouse_pos = QPointF(px, py)
                                      try:
                                          vp._refresh_snap()
                                      except Exception as exc:    # noqa: BLE001
                                          answer = {"kind": "ERROR",
                                                    "err": type(exc).__name__}
                                      else:
                                          s = vp.last_snap
                                          answer = ({"kind": "none-returned"}
                                                    if s is None else
                                                    {"kind": s.kind,
                                                     "axis": s.axis,
                                                     "x": _round(s.point.x()),
                                                     "y": _round(s.point.y()),
                                                     "z": _round(s.point.z())})
                                      fh.write(json.dumps({
                                          "scene": scene_kind, "cam": cam_name,
                                          "tool": tool_key, "alt": mode,
                                          "r": radius, "dir": i,
                                          "acq": "on" if acq else "off",
                                      "fase": "curso" if empezado else "1er-clic",
                                          **answer,
                                      }, sort_keys=True, ensure_ascii=False) + "\n")
                                      rows += 1
    win._saved_version = vp.scene.version
    win.close()
    return rows


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("-o", "--out", default="snap-matrix.jsonl")
    ap.add_argument("--directions", type=int, default=16)
    ap.add_argument("--selftest", action="store_true",
                    help="run twice and require byte-identical output")
    args = ap.parse_args()

    n = run(args.out, directions=args.directions)
    print("%d cells → %s" % (n, args.out))

    if args.selftest:
        second = args.out + ".again"
        run(second, directions=args.directions)
        a = pathlib.Path(args.out).read_bytes()
        b = pathlib.Path(second).read_bytes()
        pathlib.Path(second).unlink()
        if a != b:
            print("NOT REPRODUCIBLE — the two runs differ. "
                  "This is not a baseline yet.")
            return 1
        print("reproducible: two runs, byte for byte identical")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
