"""Tests for the orchestration controller using stub capture/recognizer."""

import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.app.controller import ScoutController  # noqa: E402
from src.capture.hotkeys import RESET  # noqa: E402
from src.capture.layout import default_1024x768  # noqa: E402
from src.engine.pool import PoolTracker, Unit, SELF_SOURCE  # noqa: E402


SET_DATA = {
    "set": 99,
    "name": "Test",
    "pool_sizes_by_cost": {"1": 30, "2": 25, "3": 18, "4": 10, "5": 9},
    "champions": [
        {"apiName": "C1", "name": "One", "cost": 1, "traits": ["A"]},
        {"apiName": "C5", "name": "Five", "cost": 5, "traits": ["B"]},
    ],
}


class FakeCapture:
    """Returns a correctly-sized blank region image; records calls."""

    def __init__(self, layout):
        self.layout = layout
        self.calls = 0

    def grab_layout_region(self, layout):
        self.calls += 1
        w, h = layout.region_size
        return np.zeros((h, w, 3), dtype=np.uint8)


class ScriptedRecognizer:
    """Returns preset units per call, ignoring the crops."""

    def __init__(self, scripts):
        self.scripts = list(scripts)
        self.i = 0

    def recognize_slots(self, crops, min_confidence=0.5):
        out = self.scripts[self.i] if self.i < len(self.scripts) else []
        self.i += 1
        return out


def make_controller(scripts):
    layout = default_1024x768()
    tracker = PoolTracker(SET_DATA)
    capture = FakeCapture(layout)
    rec = ScriptedRecognizer(scripts)
    return ScoutController(capture, rec, tracker, layout), capture, tracker


def test_capture_updates_tracker():
    ctrl, capture, tracker = make_controller([[Unit("C1", 2)]])  # 3 copies
    event = ctrl.handle_action("opp1")
    assert capture.calls == 1
    assert event.source == "opp1"
    assert event.count == 1
    assert tracker.held()["C1"] == 3


def test_rescout_same_opponent_overwrites():
    ctrl, _, tracker = make_controller([[Unit("C1", 2)], [Unit("C1", 1)]])
    ctrl.handle_action("opp1")  # 3 copies
    ctrl.handle_action("opp1")  # now 1 copy
    assert tracker.held()["C1"] == 1


def test_different_opponents_sum():
    ctrl, _, tracker = make_controller([[Unit("C1", 1)], [Unit("C1", 1)]])
    ctrl.handle_action("opp1")
    ctrl.handle_action("opp2")
    assert tracker.held()["C1"] == 2


def test_reset_clears_tally():
    ctrl, _, tracker = make_controller([[Unit("C1", 2)]])
    ctrl.handle_action("opp1")
    event = ctrl.handle_action(RESET)
    assert event.is_reset
    assert tracker.held() == {}


def test_self_capture_records_shop_separately():
    # board/bench units counted; shop recognized but NOT added to tally
    scripts = [
        [Unit("C1", 1)],   # board+bench recognition for self
        [Unit("C5", 1)],   # shop recognition for self (display only)
    ]
    ctrl, _, tracker = make_controller(scripts)
    event = ctrl.handle_action(SELF_SOURCE)
    assert tracker.held().get("C1") == 1
    assert tracker.held().get("C5") is None  # shop not counted
    assert [u.api_name for u in event.shop] == ["C5"]
    assert ctrl.last_shop == event.shop


def test_process_image_crops_region_and_updates():
    ctrl, _, tracker = make_controller([[Unit("C1", 1)]])
    w, h = ctrl.layout.region_size
    full = np.zeros((h, w, 3), dtype=np.uint8)  # region == full window here
    event = ctrl.process_image(full, "opp2")
    assert event.source == "opp2"
    assert tracker.held()["C1"] == 1


def test_process_image_rejects_too_small_image():
    ctrl, _, _ = make_controller([[Unit("C1", 1)]])
    ctrl.layout.region = (0, 0, 500, 500)  # bigger than the tiny image below
    tiny = np.zeros((100, 100, 3), dtype=np.uint8)
    try:
        ctrl.process_image(tiny, "opp1")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_recalibrate_updates_region_live():
    ctrl, _, _ = make_controller([])
    new = ctrl.recalibrate((10, 20, 110, 220))
    assert new == (10, 20, 110, 220)
    assert ctrl.layout.region == (10, 20, 110, 220)


def test_recalibrate_persists_to_layout_path(tmp_path):
    from src.capture.layout import Layout, default_1024x768

    path = tmp_path / "layout.json"
    default_1024x768().save(str(path))
    layout = Layout.load(str(path))
    tracker = PoolTracker(SET_DATA)
    ctrl = ScoutController(FakeCapture(layout), ScriptedRecognizer([]), tracker,
                           layout, layout_path=str(path))
    ctrl.recalibrate((5, 6, 1029, 774))
    # reload from disk: the new region survived
    reloaded = Layout.load(str(path))
    assert reloaded.region == (5, 6, 1029, 774)
    # grid fractions unchanged -> slots still computed relative to new region
    assert reloaded.slot_rects() == layout.slot_rects()


def test_recalibrate_coerces_to_ints():
    ctrl, _, _ = make_controller([])
    new = ctrl.recalibrate((1.9, 2.1, 100.5, 200.0))
    assert new == (1, 2, 100, 200)
    assert all(isinstance(v, int) for v in ctrl.layout.region)


def test_report_reflects_remaining():
    ctrl, _, _ = make_controller([[Unit("C5", 3)]])  # 9 copies = whole 5-cost pool
    ctrl.handle_action("opp1")
    report = {r.api_name: r for r in ctrl.report()}
    assert report["C5"].remaining == 0
    assert report["C1"].remaining == 30
