# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""The Linux bundle leaves the libraries the host's graphics driver also
loads to the host (issue #6): the X client libraries, and since v0.3.21
the C++ runtime and GLib — PyInstaller shipped the CI runner's
``libstdc++`` first in the process, and an NVIDIA driver built against a
newer one could not load, so GLX had no vendor and Qt aborted."""
from __future__ import annotations

import re
from pathlib import Path

SPEC = Path(__file__).resolve().parents[1] / "ingetrazo.spec"


def _host_only() -> set[str]:
    text = SPEC.read_text()
    m = re.search(r"_HOST_ONLY = \{([^}]*)\}", text)
    assert m, "the spec lost its host-only library set"
    return set(re.findall(r"'([^']+)'", m.group(1)))


def test_the_bundle_never_carries_the_driver_side_libraries():
    host = _host_only()
    for name in ("libX11.so.6", "libX11-xcb.so.1", "libxcb-glx.so.0",
                 "libstdc++.so.6", "libgcc_s.so.1", "libglib-2.0.so.0"):
        assert name in host, name
