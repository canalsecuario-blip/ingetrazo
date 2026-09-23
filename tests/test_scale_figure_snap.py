"""The scale figure offers ONE snap, its feet (Rafael, revision 4: «me está
cogiendo el paisano»): its base corners, midpoints, head and the two lines
through it stole the inference from the drawing around the origin."""
from __future__ import annotations

from PySide6.QtWidgets import QApplication

_app = QApplication.instance() or QApplication([])


def test_the_scale_figure_snaps_only_at_its_feet():
    from views.main_window import MainWindow
    win = MainWindow()
    vp = win.viewport
    assert any(getattr(g, "billboard", False) for g in vp.scene.groups)
    snaps = vp._billboard_snap_edges()
    assert len(snaps) == 1
    feet = snaps[0]
    assert feet.a == feet.b                       # a point, not a line
    assert abs(feet.a.z()) < 1e-6                 # on the ground
    assert abs(feet.a.x() + 0.65) < 0.05 and abs(feet.a.y() + 0.60) < 0.05
    win._saved_version = vp.scene.version
    win.close()
