# SPDX-License-Identifier: GPL-3.0-or-later
# Copyright (C) 2026 Marco Sumari Tellez and IngeTrazo contributors.
"""AppImage desktop integration (Rafael's review, 2026-09-10: the
AppImages ran but brought no launcher, no icon)."""
from __future__ import annotations

from pathlib import Path

from core import appimage


def test_not_an_appimage_without_the_runtime_variables(monkeypatch):
    monkeypatch.delenv("APPIMAGE", raising=False)
    assert appimage.appimage_path() is None


def test_integrate_writes_launcher_and_icon_pointing_at_the_file(tmp_path, monkeypatch):
    img = tmp_path / "IngeTrazo-0.3.20-x86_64.AppImage"
    img.write_bytes(b"AI")
    appdir = tmp_path / "AppDir"
    appdir.mkdir()
    (appdir / "ingetrazo.png").write_bytes(b"\x89PNG")
    data = tmp_path / "data"
    monkeypatch.setenv("APPIMAGE", str(img))
    monkeypatch.setenv("APPDIR", str(appdir))
    monkeypatch.setenv("XDG_DATA_HOME", str(data))
    monkeypatch.setattr(appimage, "_refresh_caches", lambda: None)
    assert appimage.appimage_path() == img
    assert not appimage.is_integrated(img)
    f = appimage.integrate(img)
    assert f == data / "applications" / "ingetrazo.desktop"
    text = f.read_text()
    assert f'Exec="{img}" %f' in text and f"TryExec={img}" in text
    assert "Icon=ingetrazo" in text and "application/x-ingetrazo" in text
    assert (data / "icons/hicolor/256x256/apps/ingetrazo.png").read_bytes() == b"\x89PNG"
    assert appimage.is_integrated(img)
    # a moved AppImage reads as not integrated (the launcher would be stale)
    assert not appimage.is_integrated(tmp_path / "elsewhere.AppImage")
    appimage.remove()
    assert not f.exists() and not (data / "icons/hicolor/256x256/apps/ingetrazo.png").exists()
