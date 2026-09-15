# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""Which Qt platform plugin to start on.

Measured on Marco's laptop (2026-09-14, Radeon 780M, GNOME Wayland with the
display at 125 %): under the native Wayland plugin the viewport's frames ran
p90 149 ms with the same model that gave p90 30 ms under ``xcb`` (XWayland) —
Qt composes a QOpenGLWidget window through a slow path when the output scale
is fractional. So a Wayland session whose configured monitor scale is not a
whole number starts under ``xcb`` unless the user says otherwise
(Preferences ▸ General ▸ Graphics server, or ``QT_QPA_PLATFORM`` set by hand,
which always wins). ``xwayland-native-scaling`` keeps it crisp on GNOME 46+.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

#: Preference values (QSettings ``general/platform``).
AUTO, WAYLAND, XCB = "auto", "wayland", "xcb"


def _monitors_xml_scales(home: Path) -> list[float]:
    """The ``<scale>`` values GNOME writes in ``~/.config/monitors.xml``."""
    path = home / ".config" / "monitors.xml"
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return []
    return [float(v) for v in re.findall(r"<scale>\s*([0-9.]+)\s*</scale>", text)]


def _kwin_scales(home: Path) -> list[float]:
    """The ``scale`` values KDE writes in ``~/.config/kwinoutputconfig.json``."""
    path = home / ".config" / "kwinoutputconfig.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    out: list[float] = []

    def walk(node):
        if isinstance(node, dict):
            for k, v in node.items():
                if k == "scale" and isinstance(v, (int, float)):
                    out.append(float(v))
                else:
                    walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)
    walk(data)
    return out


def fractional_scale_configured(home: Path | None = None) -> bool:
    """Whether any configured monitor uses a non-integer scale (125 %, 150 %…)."""
    home = home or Path.home()
    scales = _monitors_xml_scales(home) + _kwin_scales(home)
    return any(abs(s - round(s)) > 1e-6 for s in scales)


def choose_platform(preference: str, env: dict | None = None,
                    home: Path | None = None) -> str | None:
    """The plugin to force through ``QT_QPA_PLATFORM``, or ``None`` to leave
    Qt's own choice. An explicit ``QT_QPA_PLATFORM`` in the environment is
    never overridden."""
    env = os.environ if env is None else env
    if env.get("QT_QPA_PLATFORM"):
        return None
    pref = (preference or AUTO).lower()
    if pref == XCB:
        return XCB if env.get("DISPLAY") else None
    if pref == WAYLAND:
        return None
    if env.get("XDG_SESSION_TYPE", "").lower() != "wayland":
        return None
    if not env.get("DISPLAY"):
        return None                      # no XWayland to fall back to
    return XCB if fractional_scale_configured(home) else None


def apply_platform_preference() -> str | None:
    """Called BEFORE the QApplication exists: reads the preference and sets
    ``QT_QPA_PLATFORM`` when the choice says so. Returns what was set."""
    from PySide6.QtCore import QCoreApplication, QSettings
    QCoreApplication.setOrganizationName("IngeTrazo")
    QCoreApplication.setApplicationName("IngeTrazo")
    pref = str(QSettings().value("general/platform", AUTO) or AUTO)
    chosen = choose_platform(pref)
    if chosen:
        os.environ["QT_QPA_PLATFORM"] = chosen
    return chosen
