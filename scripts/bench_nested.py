"""Benchmark: editar grupos anidados sobre la Plaza Yanque, medido con reloj.
Uso: cd <checkout> && <venv python> scripts/bench_nested.py <igz> <etiqueta> <salida.json>
Entra y sale por niveles (contenedor → banca → listón), mueve un hijo en cada
nivel y mueve geometría suelta dentro del último. Ventana GL real (xcb)."""
import os, sys, json, time, statistics as st
os.environ["QT_QPA_PLATFORM"] = "xcb"
sys.path.insert(0, os.getcwd())
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QVector3D
app = QApplication([])
from views.main_window import MainWindow
from core.history import MoveGroupCommand, MoveVerticesCommand
igz, label, out = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
res = {"label": label, "commit": os.popen("git rev-parse --short HEAD").read().strip()}
def timed(fn, n=1):
    ts = []
    for _ in range(n):
        t0 = time.perf_counter(); fn(); ts.append((time.perf_counter() - t0) * 1000.0)
    return {"median_ms": round(st.median(ts), 2), "max_ms": round(max(ts), 2), "n": n}
win = MainWindow(); vp = win.viewport
win.resize(1280, 800); win.show()
for _ in range(20):
    app.processEvents(); time.sleep(0.05)
    if vp._gl is not None:
        break
win.open_path(igz); app.processEvents()
sc = vp.scene
lo, hi = sc.bounds(); vp.camera.fit_to(lo, hi)
def paint_now():
    vp.makeCurrent()
    try:
        vp.paintGL()
    finally:
        vp.doneCurrent()
paint_now()
def path():
    """[contenedor, banca, listón]: el primer hijo con hijos con un nieto con caras."""
    for top in sc.groups:
        for child in (top.children or []):
            if child.children:
                for grand in child.children:
                    if grand.mesh is not None and grand.mesh.faces:
                        return [top, child, grand]
    return None
levels = path()
res["path"] = [g.name for g in levels]
win._activate_tool("select")
res["enter"] = []; res["leave"] = []; res["move_child"] = []
for depth, g in enumerate(levels):
    res["enter"].append(timed(lambda: (vp.begin_group_edit(g), paint_now())))
    # mover un hijo del nivel abierto (o geometría suelta en el último)
    kids = [c for c in (g.children or []) if c.mesh is not None]
    if kids:
        child = kids[0]
        res["move_child"].append(timed(lambda: (vp.history.execute(MoveGroupCommand(child, QVector3D(0.02, 0, 0))), paint_now()), 5))
    else:
        verts = [QVector3D(v.position) for v in list(sc.mesh.vertices)[:8]]
        res["move_child"].append(timed(lambda: (vp.history.execute(MoveVerticesCommand(verts, QVector3D(0.0, 0, 0.01))), paint_now()), 5))
    res["move_child"][-1]["what"] = ("group " + kids[0].name) if kids else "loose vertices"
for depth in range(len(levels)):
    res["leave"].append(timed(lambda: (vp.end_one_group_edit(), paint_now())))
json.dump(res, open(out, "w"), indent=1)
print(json.dumps(res, indent=1))
win._saved_version = sc.version; win.close(); app.quit()
