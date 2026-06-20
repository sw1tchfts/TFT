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
