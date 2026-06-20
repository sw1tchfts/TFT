"""Always-on-top dashboard showing copies remaining by contestability.

Thin PySide6 layer; lazy-imported so the rest of the app stays headless-friendly.
Hotkeys fire on a background thread (pynput), so capture results are marshalled
to the UI thread via a Qt signal.
"""

from __future__ import annotations

from ..app.controller import ScoutController
from ..engine.pool import OPPONENT_SOURCES, SELF_SOURCE


def run_dashboard(controller: ScoutController) -> int:
    from PySide6 import QtCore, QtGui, QtWidgets

    from ..capture.hotkeys import RESET, HotkeyManager

    COST_COLORS = {
        1: "#9e9e9e", 2: "#1faa59", 3: "#2f6fed",
        4: "#a64ddb", 5: "#e0a92b",
    }

    class Bridge(QtCore.QObject):
        captured = QtCore.Signal(str)  # emits the action that just happened

    class Dashboard(QtWidgets.QWidget):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("TFT Scout")
            self.setWindowFlags(QtCore.Qt.WindowStaysOnTopHint)
            self.resize(420, 640)

            layout = QtWidgets.QVBoxLayout(self)
            self.status = QtWidgets.QLabel("Press 1-7 to scout, 0 for self, ` to reset")
            layout.addWidget(self.status)

            # calibration controls
            cal_row = QtWidgets.QHBoxLayout()
            self.cal_btn = QtWidgets.QPushButton("Calibrate region")
            self.cal_btn.clicked.connect(self.calibrate)
            self.grid_btn = QtWidgets.QPushButton("Show grid")
            self.grid_btn.clicked.connect(self.show_grid)
            cal_row.addWidget(self.cal_btn)
            cal_row.addWidget(self.grid_btn)
            layout.addLayout(cal_row)

            self.cost_filter = QtWidgets.QComboBox()
            self.cost_filter.addItem("All costs", None)
            for c in (1, 2, 3, 4, 5):
                self.cost_filter.addItem(f"{c}-cost", c)
            self.cost_filter.currentIndexChanged.connect(self.refresh)
            layout.addWidget(self.cost_filter)

            self.table = QtWidgets.QTableWidget(0, 4)
            self.table.setHorizontalHeaderLabels(["Champion", "Cost", "Left", "Held"])
            self.table.horizontalHeader().setStretchLastSection(True)
            self.table.verticalHeader().setVisible(False)
            layout.addWidget(self.table)

            self.refresh()

        def calibrate(self):
            """Drag a new capture region; persist + apply it live."""
            from ..capture.calibrate import _build_selector

            RegionSelector = _build_selector()
            self._selector = RegionSelector()  # keep a ref so it isn't GC'd
            self._selector.finished.connect(self._on_calibrated)
            self.hide()  # get the dashboard out of the way of the overlay
            self._selector.show()

        def _on_calibrated(self):
            self.show()
            region = self._selector.selected
            if region is not None:
                region = controller.recalibrate(region)
                w, h = region[2] - region[0], region[3] - region[1]
                self.status.setText(f"Region set: {w}x{h} (saved)")
            else:
                self.status.setText("Calibration cancelled")

        def show_grid(self):
            """Overlay the current slot grid on screen for a few seconds."""
            from ..capture.calibrate import _build_grid_overlay

            GridOverlay = _build_grid_overlay()
            self._grid = GridOverlay(controller.layout)
            self._grid.show()
            QtCore.QTimer.singleShot(4000, self._grid.close)

        def on_capture(self, action: str):
            ev = controller.last_event
            if action == RESET:
                self.status.setText("Pool reset")
            elif ev is not None:
                self.status.setText(f"{action}: {ev.count} units")
            self.refresh()

        def refresh(self):
            cost = self.cost_filter.currentData()
            rows = [r for r in controller.report() if cost is None or r.cost == cost]
            self.table.setRowCount(len(rows))
            for i, r in enumerate(rows):
                name = QtWidgets.QTableWidgetItem(r.name)
                color = QtGui.QColor(COST_COLORS.get(r.cost, "#888"))
                name.setForeground(color)
                self.table.setItem(i, 0, name)
                self.table.setItem(i, 1, QtWidgets.QTableWidgetItem(str(r.cost)))
                left = QtWidgets.QTableWidgetItem(f"{r.remaining}/{r.total}")
                if r.over_counted:
                    left.setForeground(QtGui.QColor("#d33"))
                self.table.setItem(i, 2, left)
                self.table.setItem(i, 3, QtWidgets.QTableWidgetItem(str(r.held)))

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    bridge = Bridge()
    dash = Dashboard()
    bridge.captured.connect(dash.on_capture)

    def on_action(action: str):
        controller.handle_action(action)
        bridge.captured.emit(action)  # thread-safe queued signal

    hotkeys = HotkeyManager(on_action)
    hotkeys.start()
    dash.show()
    try:
        return app.exec()
    finally:
        hotkeys.stop()
