"""Orchestration: hotkey action -> capture -> slice -> recognize -> pool update.

The controller is dependency-injected (capture, recognizer, tracker, layout) so
the full flow is unit-testable headless with stubs — no screen, torch, or GUI
required. `build_controller()` wires the real components with lazy imports.

Source semantics:
    opp1..opp7  -> count board + bench, tagged to that opponent (overwrites)
    self        -> count board + bench; shop is recognized for *display only*
                   (shop copies return to the pool on reroll, so counting them
                   would inflate the tally)
    reset       -> clear the running tally
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..capture.layout import Layout
from ..capture.slicer import slice_image
from ..engine.pool import SELF_SOURCE, Unit
from ..capture.hotkeys import RESET

# Groups counted into the permanent pool tally, per source kind.
COUNTED_GROUPS = ("board", "bench")
SHOP_GROUP = "shop"


@dataclass
class CaptureEvent:
    source: str
    units: list[Unit] = field(default_factory=list)
    shop: list[Unit] = field(default_factory=list)
    is_reset: bool = False

    @property
    def count(self) -> int:
        return len(self.units)


class ScoutController:
    def __init__(self, capture, recognizer, tracker, layout: Layout,
                 min_confidence: float = 0.5):
        self.capture = capture
        self.recognizer = recognizer
        self.tracker = tracker
        self.layout = layout
        self.min_confidence = min_confidence
        self.last_event: CaptureEvent | None = None
        self.last_shop: list[Unit] = []

    def handle_action(self, action: str) -> CaptureEvent:
        if action == RESET:
            self.tracker.reset()
            self.last_shop = []
            event = CaptureEvent(source=RESET, is_reset=True)
            self.last_event = event
            return event

        region_image = self.capture.grab_layout_region(self.layout)
        return self._ingest(region_image, action)

    def process_image(self, full_image, action: str) -> CaptureEvent:
        """Process a saved screenshot (e.g. loaded from a PNG file).

        `full_image` is a full-frame capture; the layout region is cropped out of
        it using screen coordinates, then handled like a live capture. Useful for
        offline testing and calibration without the game running.
        """
        if action == RESET:
            return self.handle_action(RESET)
        region_image = self._crop_region(full_image)
        return self._ingest(region_image, action)

    def _crop_region(self, full_image):
        """Crop the layout region (screen coords) out of a full-frame image."""
        x0, y0, x1, y1 = self.layout.region
        h, w = full_image.shape[0], full_image.shape[1]
        if x1 > w or y1 > h:
            raise ValueError(
                f"layout region {self.layout.region} exceeds image size {(w, h)}; "
                "use an image at least as large as the region, or recalibrate"
            )
        return full_image[y0:y1, x0:x1]

    def _ingest(self, region_image, action: str) -> CaptureEvent:
        # available groups depend on which exist in this layout
        groups = [g for g in COUNTED_GROUPS if g in self.layout.groups]
        crops = slice_image(region_image, self.layout, groups)
        units = self.recognizer.recognize_slots(crops, self.min_confidence)
        self.tracker.update_source(action, units)

        shop: list[Unit] = []
        if action == SELF_SOURCE and SHOP_GROUP in self.layout.groups:
            shop_crops = slice_image(region_image, self.layout, [SHOP_GROUP])
            shop = self.recognizer.recognize_slots(shop_crops, self.min_confidence)
            self.last_shop = shop

        event = CaptureEvent(source=action, units=units, shop=shop)
        self.last_event = event
        return event

    def report(self, sort_by: str = "remaining"):
        return self.tracker.report(sort_by=sort_by)


def build_controller(layout_path: str | None = None,
                     set_data_path: str | None = None,
                     min_confidence: float = 0.5) -> ScoutController:
    """Construct a controller with the real capture/recognizer/tracker."""
    import json
    import os

    from ..capture.layout import Layout
    from ..capture.screen import ScreenCapture
    from ..engine.pool import PoolTracker
    from ..model.infer import ChampionRecognizer

    root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    layout_path = layout_path or os.path.join(root, "config", "layout_1024x768.json")
    set_data_path = set_data_path or os.path.join(root, "config", "set_data.json")

    layout = Layout.load(layout_path)
    with open(set_data_path) as fh:
        set_data = json.load(fh)
    tracker = PoolTracker(set_data)
    recognizer = ChampionRecognizer()
    capture = ScreenCapture()
    return ScoutController(capture, recognizer, tracker, layout, min_confidence)
