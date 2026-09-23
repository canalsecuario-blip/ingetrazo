"""Copy/Paste between IngeTrazo windows (issue #76): the model clipboard
travels through the system clipboard as a small ``.igz``-based payload."""
from __future__ import annotations

import pytest
from PySide6.QtGui import QMatrix4x4, QVector3D as V
from PySide6.QtWidgets import QApplication

from core.group import Group, copy_group
from core.mesh import Mesh
from formats import clip


@pytest.fixture(scope="module")
def app():
    return QApplication.instance() or QApplication([])


def _box_group(x: float) -> Group:
    m = Mesh()
    pts = [V(x, 0, 0), V(x + 1, 0, 0), V(x + 1, 1, 0), V(x, 1, 0)]
    m.add_face(pts)
    g = Group(m)
    g.name = f"box {x}"
    return g


def _clip():
    square = [V(0, 0, 0), V(2, 0, 0), V(2, 2, 0), V(0, 2, 0)]
    hole = [V(0.5, 0.5, 0), V(1, 0.5, 0), V(1, 1, 0), V(0.5, 1, 0)]
    classic = _box_group(5)
    placed = copy_group(_box_group(9))
    xf = QMatrix4x4()
    xf.translate(0, 0, 3)
    placed.xform = xf
    return {
        "faces": [(square, [hole], {"color": (0.8, 0.2, 0.1)})],
        "edges": [(V(0, 0, 0), V(0, 0, 4), True, None)],
        "groups": [classic, placed],
        "ref": V(0, 0, 0),
    }


def test_the_clipboard_survives_the_trip(app):
    out = clip.decode(clip.encode(_clip()))
    assert out is not None
    (loop, holes, attrs), = out["faces"]
    assert len(loop) == 4 and len(holes) == 1
    assert attrs["color"] == pytest.approx((0.8, 0.2, 0.1))
    (a, b, soft, curve), = out["edges"]
    assert (a, b, soft, curve) == (V(0, 0, 0), V(0, 0, 4), True, None)
    assert out["ref"] == V(0, 0, 0)
    assert len(out["groups"]) == 2
    # Every group arrives as a placement (the paste tool stamps siblings).
    assert all(g.xform is not None for g in out["groups"])
    lifted = out["groups"][1]
    assert lifted.xform.map(V(0, 0, 0)).z() == pytest.approx(3)


def test_garbage_is_not_a_clipboard(app):
    assert clip.decode(b"not a zip") is None


def test_this_windows_own_copy_is_not_foreign(app):
    clip.publish(_clip())
    assert clip.available()
    assert clip.foreign() is None


def test_the_offer_is_rendered_on_demand(app):
    mime = clip.ClipMime(_clip())
    assert mime.formats() == [clip.MIME]
    data = mime.retrieveData(clip.MIME, None)
    assert clip.decode(data.data()) is not None
    assert mime.retrieveData("text/plain", None) is None


@pytest.mark.parametrize("env, expect", [
    ({"APPIMAGE": "/tmp/IngeTrazo.AppImage"},
     ["/tmp/IngeTrazo.AppImage", "--new-window"]),
    ({"FLATPAK_ID": "com.ingetrazo.IngeTrazo"},
     ["flatpak-spawn", "ingetrazo", "--new-window"]),
])
def test_a_new_window_starts_from_its_own_package(monkeypatch, env, expect):
    from views.main_window import MainWindow
    monkeypatch.delenv("APPIMAGE", raising=False)
    monkeypatch.delenv("FLATPAK_ID", raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    assert MainWindow._new_window_command() == expect


def test_a_new_window_from_the_repo_runs_main_py(monkeypatch):
    from views.main_window import MainWindow
    monkeypatch.delenv("APPIMAGE", raising=False)
    monkeypatch.delenv("FLATPAK_ID", raising=False)
    cmd = MainWindow._new_window_command()
    assert cmd[-2].endswith("main.py") and cmd[-1] == "--new-window"


def test_quitting_leaves_the_copy_as_plain_data(app):
    clip.publish(_clip())
    clip.flush()
    md = QApplication.clipboard().mimeData()
    assert not isinstance(md, clip.ClipMime)
    assert clip.decode(md.data(clip.MIME).data()) is not None
