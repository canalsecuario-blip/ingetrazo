# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""Differential validation harness for IngeTrazo's .skp reader.

Ground truth is a COLLADA file **exported from the original program** by
whoever owns the model (File ▸ Export ▸ 3D Model ▸ .dae), placed next to
the .skp or given with ``--dae``. The harness loads it into a headless
``Scene``, loads the .skp through IngeTrazo's own reader
(``formats/skp.py``), and diffs structural fingerprints (counts, bbox,
materials, groups).

Nothing proprietary runs here. (Until 2026-09-28 the ground truth came
from the former external converter; that path was removed.)

Usage::

    python scripts/skp_diff.py path/to/model.skp [--dae model.dae] [--json] [--tol 0.001]

No GL is needed — everything here is headless (``Scene`` + ``load_dae``).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


# ---- fingerprint ---------------------------------------------------------------

def fingerprint(scene) -> dict:
    """A structural summary of a loaded ``Scene`` — the comparable signature of
    a parse: geometry counts, bounding box, distinct materials/textures, and the
    group breakdown. Deliberately parser-agnostic (no identity, no ordering)."""
    from formats.meshexport import world_faces

    from PySide6.QtGui import QVector3D

    faces = list(world_faces(scene))
    tris = 0
    area = 0.0
    vkeys = set()
    colors = set()
    textures = set()
    xmin = ymin = zmin = float("inf")
    xmax = ymax = zmax = float("-inf")
    for f in faces:
        for a, b, c in f.triangulate():
            tris += 1
            area += QVector3D.crossProduct(b - a, c - a).length() / 2.0
        tex = f.attrs.get("texture")
        if tex is not None and tex.get("path"):
            textures.add(Path(tex["path"]).name)
        else:
            colors.add(tuple(round(c, 4) for c in (f.attrs.get("color")
                                                   or (0.96, 0.95, 0.925))))
        for v in f.vertices:   # Face.vertices is a property → list[QVector3D]
            p = (round(v.x(), 4), round(v.y(), 4), round(v.z(), 4))
            vkeys.add(p)
            xmin, ymin, zmin = min(xmin, p[0]), min(ymin, p[1]), min(zmin, p[2])
            xmax, ymax, zmax = max(xmax, p[0]), max(ymax, p[1]), max(zmax, p[2])

    groups = getattr(scene, "groups", [])
    bbox = None
    if faces:
        bbox = {"min": [xmin, ymin, zmin], "max": [xmax, ymax, zmax],
                "size": [xmax - xmin, ymax - ymin, zmax - zmin]}
    return {
        "faces": len(faces),
        "triangles": tris,
        "vertices": len(vkeys),
        # Total surface area — the fusion-invariant completeness metric.
        # Face/triangle/vertex counts shift with post-processing (coplanar
        # fusion, welding, double-face dedupe), but the area of the same
        # geometry does not: equal areas = complete geometry.
        "area_m2": round(area, 3),
        "materials": len(colors),
        "textures": len(textures),
        "groups": len(groups),
        "group_names": sorted(g.name for g in groups if getattr(g, "name", None)),
        "bbox": bbox,
    }


def compare(ground: dict, candidate: dict, tol: float = 1e-3) -> list[str]:
    """Human-readable discrepancies between two fingerprints. Surface area is
    the hard completeness metric (fusion-invariant); when areas agree within
    0.5%, count deltas are labelled as post-processing differences rather than
    lost geometry. The bbox is checked per axis against ``tol`` metres. An
    empty list means the parses agree structurally."""
    issues: list[str] = []
    ga, ca = ground.get("area_m2", 0.0), candidate.get("area_m2", 0.0)
    area_rel = abs(ca - ga) / ga if ga else (0.0 if not ca else float("inf"))
    areas_agree = area_rel <= 0.005
    if not areas_agree:
        issues.append(f"area_m2: ground={ga} candidate={ca} "
                      f"({area_rel * 100:.2f}% — geometry incomplete)")
    for key in ("faces", "triangles", "vertices", "materials", "textures",
                "groups"):
        a, b = ground.get(key, 0), candidate.get(key, 0)
        if a != b:
            rel = (abs(a - b) / a * 100) if a else float("inf")
            note = (" [areas agree: post-processing, not lost geometry]"
                    if areas_agree and key in ("faces", "triangles", "vertices")
                    else "")
            issues.append(f"{key}: ground={a} candidate={b} "
                          f"(Δ={b - a}, {rel:.1f}%){note}")
    gb, cb = ground.get("bbox"), candidate.get("bbox")
    if gb and cb:
        for axis, i in (("x", 0), ("y", 1), ("z", 2)):
            for bound in ("min", "max"):
                d = abs(gb[bound][i] - cb[bound][i])
                if d > tol:
                    issues.append(f"bbox.{bound}.{axis}: "
                                  f"ground={gb[bound][i]:.4f} "
                                  f"candidate={cb[bound][i]:.4f} (Δ={d:.4f} m)")
    elif gb != cb:
        issues.append(f"bbox: ground={gb} candidate={cb}")
    return issues


# ---- loaders -------------------------------------------------------------------

def load_ground_truth(dae: Path):
    """Load the reference COLLADA export of the model into a fresh Scene."""
    from core.scene import Scene
    from formats import dae as dae_format

    if not dae.exists():
        raise RuntimeError(
            f"No ground truth: {dae} does not exist. Put a COLLADA (.dae) "
            "export of the model next to the .skp, or pass --dae.")
    scene = Scene()
    dae_format.load_dae(scene, dae)
    return scene


def load_candidate(skp: Path):
    """Load ``skp`` through the pure-backend seam, or ``None`` when no backend
    can read it yet (``NeedsConverter``)."""
    from core.scene import Scene
    from formats import skp as skp_format

    scene = Scene()
    try:
        skp_format.load_skp(scene, skp)
    except skp_format.NeedsConverter:
        return None
    return scene


# ---- CLI -----------------------------------------------------------------------

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Diff a .skp: a reference "
                                             "COLLADA export vs IngeTrazo's reader.")
    ap.add_argument("skp", type=Path, help="path to the .skp file")
    ap.add_argument("--dae", type=Path, default=None,
                    help="a COLLADA export of it (default: next to the .skp)")
    ap.add_argument("--json", action="store_true", help="machine-readable output")
    ap.add_argument("--tol", type=float, default=1e-3,
                    help="bbox tolerance in metres (default 1e-3)")
    args = ap.parse_args(argv)

    if not args.skp.exists():
        print(f"No such file: {args.skp}", file=sys.stderr)
        return 2

    ground = fingerprint(load_ground_truth(args.dae or args.skp.with_suffix(".dae")))
    from formats import skp as skp_format
    fmt = skp_format.detect_format(args.skp)
    cand_scene = load_candidate(args.skp)
    candidate = fingerprint(cand_scene) if cand_scene is not None else None

    if args.json:
        print(json.dumps({"format": fmt, "ground_truth": ground,
                          "candidate": candidate,
                          "diff": compare(ground, candidate, args.tol)
                          if candidate else None}, indent=2))
        return 0

    print(f"File: {args.skp.name}   format={fmt}")
    print("\n[ground truth — reference COLLADA export]")
    for k, v in ground.items():
        print(f"  {k}: {v}")
    if candidate is None:
        wired = [n for n, ok in skp_format.backends_status() if ok]
        print("\n[candidate — pure backend]")
        print("  unavailable: no pure backend supports this file yet "
              f"(wired: {wired or 'none'}).")
        print("  Only the COLLADA side was loaded.")
        return 0
    print("\n[candidate — pure backend]")
    for k, v in candidate.items():
        print(f"  {k}: {v}")
    issues = compare(ground, candidate, args.tol)
    print("\n[diff]")
    if not issues:
        print("  ✓ parses agree structurally")
    else:
        for i in issues:
            print(f"  ✗ {i}")
    return 1 if issues else 0


if __name__ == "__main__":
    raise SystemExit(main())
