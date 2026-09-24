"""The orbit never sticks to the mouse (Andrés Rodríguez, Windows 11,
0.5.0: «el orbital se mantiene activo aunque cambie a cualquier otra
herramienta… no se desactiva con nada»). A camera drag is remembered from
the press until its release; when that release was lost, every mouse move
orbited the view, whatever tool was picked."""
from __future__ import annotations

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtWidgets import QApplication

_app = QApplication.instance() or QApplication([])


def _move(vp, x, y, buttons=Qt.NoButton):
    ev = QMouseEvent(QMouseEvent.MouseMove, QPointF(x, y), QPointF(x, y),
                     Qt.NoButton, buttons, Qt.NoModifier)
    vp.mouseMoveEvent(ev)


def _window():
    from views.main_window import MainWindow
    win = MainWindow()
    win.viewport.resize(800, 600)
    return win


def _pose(cam):
    return (round(cam.yaw, 9), round(cam.pitch, 9))


def test_a_lost_release_does_not_leave_the_orbit_on():
    win = _window()
    vp = win.viewport
    vp._last_pos = QPoint(100, 100)          # a wheel-drag whose release was lost
    before = _pose(vp.camera)
    _move(vp, 180, 140)                      # plain move, no button held
    assert _pose(vp.camera) == before
    assert vp._last_pos is None
    win._saved_version = vp.scene.version
    win.close()


def test_a_real_drag_still_orbits():
    win = _window()
    vp = win.viewport
    vp._last_pos = QPoint(100, 100)
    before = _pose(vp.camera)
    _move(vp, 180, 140, Qt.MiddleButton)     # the wheel is held
    assert _pose(vp.camera) != before
    win._saved_version = vp.scene.version
    win.close()


def test_picking_a_tool_ends_a_camera_drag():
    win = _window()
    vp = win.viewport
    vp.set_nav_mode("orbit")
    vp._last_pos = QPoint(100, 100)
    win._activate_tool("paint")
    assert vp.nav_mode is None and vp._last_pos is None
    win._saved_version = vp.scene.version
    win.close()
