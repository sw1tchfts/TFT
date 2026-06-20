"""Drag-to-calibrate the capture region.

Shows a fullscreen translucent overlay; you drag a rectangle over the TFT play
area. The selected screen rect is written into a layout file (preserving the
grid fractions) so slicing maps onto your window.

PySide6 is imported lazily inside main() so the rest of the capture package is
usable headless. Run:

    python -m src.capture.calibrate --out config/layout_1024x768.json
"""

from __future__ import annotations

import argparse
import os

from .layout import Layout, default_1024x768

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DEFAULT_OUT = os.path.join(REPO_ROOT, "config", "layout_1024x768.json")


def _build_selector():
    """Construct the overlay widget class (deferred so PySide6 stays optional)."""
    from PySide6 import QtCore, QtGui, QtWidgets

    class RegionSelector(QtWidgets.QWidget):
        finished = QtCore.Signal()  # emitted on selection or cancel

        def __init__(self):
            super().__init__()
            self.setWindowFlags(
                QtCore.Qt.FramelessWindowHint
                | QtCore.Qt.WindowStaysOnTopHint
                | QtCore.Qt.Tool
            )
            self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
            self.setCursor(QtCore.Qt.CrossCursor)
            screen = QtWidgets.QApplication.primaryScreen().geometry()
            self.setGeometry(screen)
            self._origin = None
            self._rubber = QtWidgets.QRubberBand(
                QtWidgets.QRubberBand.Rectangle, self
            )
            self.selected: tuple[int, int, int, int] | None = None

        def paintEvent(self, _event):
            painter = QtGui.QPainter(self)
            painter.fillRect(self.rect(), QtGui.QColor(0, 0, 0, 90))
            painter.setPen(QtGui.QColor(255, 255, 255))
            painter.drawText(
                20, 30, "Drag over the TFT play area, then release. Esc to cancel."
            )

        def mousePressEvent(self, event):
            self._origin = event.position().toPoint()
            self._rubber.setGeometry(QtCore.QRect(self._origin, QtCore.QSize()))
            self._rubber.show()

        def mouseMoveEvent(self, event):
            if self._origin is not None:
                rect = QtCore.QRect(self._origin, event.position().toPoint())
                self._rubber.setGeometry(rect.normalized())

        def mouseReleaseEvent(self, event):
            if self._origin is None:
                return
            rect = QtCore.QRect(
                self._origin, event.position().toPoint()
            ).normalized()
            g = self.geometry()
            self.selected = (
                g.x() + rect.left(),
                g.y() + rect.top(),
                g.x() + rect.right(),
                g.y() + rect.bottom(),
            )
            self.close()
            self.finished.emit()

        def keyPressEvent(self, event):
            if event.key() == QtCore.Qt.Key_Escape:
                self.close()
                self.finished.emit()

    return RegionSelector


def _build_grid_overlay():
    """Overlay that outlines the current slot grid over the screen (deferred)."""
    from PySide6 import QtCore, QtGui, QtWidgets

    class GridOverlay(QtWidgets.QWidget):
        GROUP_COLORS = {
            "board": QtGui.QColor(80, 200, 255),
            "bench": QtGui.QColor(120, 255, 120),
            "shop": QtGui.QColor(255, 200, 80),
        }

        def __init__(self, layout: Layout):
            super().__init__()
            self.layout = layout
            self.setWindowFlags(
                QtCore.Qt.FramelessWindowHint
                | QtCore.Qt.WindowStaysOnTopHint
                | QtCore.Qt.Tool
            )
            self.setAttribute(QtCore.Qt.WA_TranslucentBackground)
            self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
            screen = QtWidgets.QApplication.primaryScreen().geometry()
            self.setGeometry(screen)

        def paintEvent(self, _event):
            painter = QtGui.QPainter(self)
            # region outline
            rx0, ry0, rx1, ry1 = self.layout.region
            painter.setPen(QtGui.QPen(QtGui.QColor(255, 255, 255), 2))
            painter.drawRect(rx0, ry0, rx1 - rx0, ry1 - ry0)
            # slots (converted to screen coords)
            for slot in self.layout.slots():
                color = self.GROUP_COLORS.get(slot.group, QtGui.QColor(255, 0, 0))
                painter.setPen(QtGui.QPen(color, 1))
                sx0, sy0, sx1, sy1 = self.layout.to_screen(slot.rect)
                painter.drawRect(sx0, sy0, sx1 - sx0, sy1 - sy0)
            painter.setPen(QtGui.QColor(255, 255, 255))
            painter.drawText(rx0 + 4, ry0 - 6 if ry0 > 12 else ry0 + 14,
                             "Grid preview — click or Esc to close")

        def mousePressEvent(self, _event):
            self.close()

        def keyPressEvent(self, event):
            if event.key() == QtCore.Qt.Key_Escape:
                self.close()

    return GridOverlay


def show_grid(layout: Layout, seconds: float = 4.0) -> None:
    """Show the slot grid overlaid on the screen for the given layout.

    Standalone helper: runs its own event loop and auto-closes after `seconds`.
    The dashboard uses _build_grid_overlay directly instead of this.
    """
    from PySide6 import QtCore, QtWidgets

    owns_app = QtWidgets.QApplication.instance() is None
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    GridOverlay = _build_grid_overlay()
    overlay = GridOverlay(layout)
    overlay.show()
    QtCore.QTimer.singleShot(int(seconds * 1000), overlay.close)
    if owns_app:
        QtCore.QTimer.singleShot(int(seconds * 1000) + 200, app.quit)
        app.exec()


def calibrate_region(base: Layout | None = None) -> Layout | None:
    """Open the overlay; return a Layout with the chosen region, or None."""
    from PySide6 import QtWidgets

    layout = base or default_1024x768()
    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    RegionSelector = _build_selector()
    selector = RegionSelector()
    selector.show()
    app.exec()
    if selector.selected is None:
        return None
    layout.region = selector.selected
    return layout


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", default=DEFAULT_OUT, help="layout file to write")
    ap.add_argument("--base", help="existing layout file to start from")
    args = ap.parse_args(argv)

    base = Layout.load(args.base) if args.base else None
    layout = calibrate_region(base)
    if layout is None:
        print("calibration cancelled")
        return 1
    layout.save(args.out)
    w, h = layout.region_size
    print(f"region set to {layout.region} ({w}x{h}); wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
