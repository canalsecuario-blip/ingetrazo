# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""Wayland + fractional display scale starts under xcb (measured: frames p90
149 ms vs 30 ms on the same model, Marco's laptop, 2026-09-14) — unless the
user or the environment says otherwise."""
from core.platform_choice import AUTO, WAYLAND, XCB, choose_platform, fractional_scale_configured


def _gnome_home(tmp_path, scale):
    (tmp_path / ".config").mkdir(parents=True)
    (tmp_path / ".config" / "monitors.xml").write_text(
        f"<monitors version=\"2\"><configuration><logicalmonitor>"
        f"<scale>{scale}</scale></logicalmonitor></configuration></monitors>")
    return tmp_path


def test_fractional_scale_is_read_from_gnome_and_kde(tmp_path):
    assert fractional_scale_configured(_gnome_home(tmp_path, "1.25"))
    assert not fractional_scale_configured(_gnome_home(tmp_path / "b", "2"))
    kde = tmp_path / "kde"
    (kde / ".config").mkdir(parents=True)
    (kde / ".config" / "kwinoutputconfig.json").write_text(
        '[{"data": [{"name": "eDP-1", "scale": 1.5}]}]')
    assert fractional_scale_configured(kde)
    assert not fractional_scale_configured(tmp_path / "nothing")


def test_auto_picks_xcb_only_on_wayland_with_fractional_scale_and_x11_available(tmp_path):
    home = _gnome_home(tmp_path, "1.25")
    wl = {"XDG_SESSION_TYPE": "wayland", "DISPLAY": ":0"}
    assert choose_platform(AUTO, wl, home) == XCB
    assert choose_platform(AUTO, {"XDG_SESSION_TYPE": "wayland"}, home) is None      # no XWayland
    assert choose_platform(AUTO, {"XDG_SESSION_TYPE": "x11", "DISPLAY": ":0"}, home) is None
    assert choose_platform(AUTO, wl, _gnome_home(tmp_path / "int", "2")) is None    # whole scale
    assert choose_platform(AUTO, {**wl, "QT_QPA_PLATFORM": "wayland"}, home) is None  # the env wins


def test_the_explicit_choices(tmp_path):
    home = _gnome_home(tmp_path, "1")
    wl = {"XDG_SESSION_TYPE": "wayland", "DISPLAY": ":0"}
    assert choose_platform(XCB, wl, home) == XCB
    assert choose_platform(XCB, {"XDG_SESSION_TYPE": "wayland"}, home) is None
    assert choose_platform(WAYLAND, wl, _gnome_home(tmp_path / "f", "1.25")) is None
