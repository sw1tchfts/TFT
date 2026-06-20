"""Screen capture of a region using mss.

Thin wrapper kept separate from geometry so the pure layout/slicer code stays
testable without a display. mss is imported lazily so importing this module
doesn't require the dependency until capture is actually used.
"""

from __future__ import annotations

from .layout import Layout, Rect


class ScreenCapture:
    """Grabs a fixed screen region as an RGB numpy array."""

    def __init__(self):
        self._sct = None

    def _ensure(self):
        if self._sct is None:
            import mss  # lazy import

            self._sct = mss.mss()
        return self._sct

    def grab(self, region: Rect):
        """Capture a screen-space rect (x0, y0, x1, y1) -> RGB ndarray (H,W,3)."""
        import numpy as np

        sct = self._ensure()
        x0, y0, x1, y1 = region
        monitor = {"left": x0, "top": y0, "width": x1 - x0, "height": y1 - y0}
        shot = sct.grab(monitor)
        # mss returns BGRA; drop alpha and reverse to RGB
        arr = np.asarray(shot)[:, :, :3][:, :, ::-1]
        return np.ascontiguousarray(arr)

    def grab_layout_region(self, layout: Layout):
        """Capture exactly the layout's region (region-local coords)."""
        return self.grab(layout.region)

    def close(self):
        if self._sct is not None:
            self._sct.close()
            self._sct = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
