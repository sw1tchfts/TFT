"""Tests for the pool-tracking engine."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.engine.pool import (  # noqa: E402
    PoolTracker,
    Unit,
    STAR_TO_COPIES,
    SELF_SOURCE,
)


@pytest.fixture
def set_data():
    return {
        "set": 99,
        "name": "TestSet",
        "pool_sizes_by_cost": {"1": 30, "2": 25, "3": 18, "4": 10, "5": 9},
        "champions": [
            {"apiName": "C1", "name": "Onecost", "cost": 1, "traits": ["A"]},
            {"apiName": "C2", "name": "Twocost", "cost": 2, "traits": ["B"]},
            {"apiName": "C5", "name": "Fivecost", "cost": 5, "traits": ["C"]},
        ],
    }


@pytest.fixture
def tracker(set_data):
    return PoolTracker(set_data)


def test_star_copies_mapping():
    assert STAR_TO_COPIES == {1: 1, 2: 3, 3: 9}
    assert Unit("C1", 1).copies() == 1
    assert Unit("C1", 2).copies() == 3
    assert Unit("C1", 3).copies() == 9


def test_invalid_star_raises():
    with pytest.raises(ValueError):
        Unit("C1", 4).copies()


def test_pool_total_by_cost(tracker):
    assert tracker.pool_total("C1") == 30
    assert tracker.pool_total("C2") == 25
    assert tracker.pool_total("C5") == 9


def test_empty_pool_all_remaining(tracker):
    report = {r.api_name: r for r in tracker.report()}
    assert report["C1"].remaining == 30
    assert report["C1"].held == 0
    assert report["C5"].remaining == 9


def test_single_source_counts_copies(tracker):
    tracker.update_source("opp1", [("C1", 1), ("C1", 2)])  # 1 + 3 copies
    report = {r.api_name: r for r in tracker.report()}
    assert report["C1"].held == 4
    assert report["C1"].remaining == 26


def test_three_star_counts_nine(tracker):
    tracker.update_source("opp1", [("C5", 3)])
    report = {r.api_name: r for r in tracker.report()}
    assert report["C5"].held == 9
    assert report["C5"].remaining == 0


def test_multiple_sources_sum(tracker):
    tracker.update_source("opp1", [("C1", 2)])      # 3
    tracker.update_source("opp2", [("C1", 1)])      # 1
    tracker.update_source(SELF_SOURCE, [("C1", 1)])  # 1
    assert tracker.held()["C1"] == 5


def test_rescout_overwrites_not_adds(tracker):
    tracker.update_source("opp1", [("C1", 2)])  # 3 copies
    assert tracker.held()["C1"] == 3
    # opponent sold a copy; re-scout shows fewer
    tracker.update_source("opp1", [("C1", 1)])  # now 1 copy
    assert tracker.held()["C1"] == 1


def test_clear_source(tracker):
    tracker.update_source("opp1", [("C1", 2)])
    tracker.clear_source("opp1")
    assert tracker.held().get("C1", 0) == 0


def test_over_count_clamps_and_flags(tracker):
    # 4 three-stars = 36 copies of a 1-cost (pool only 30) -> detection error
    tracker.update_source("opp1", [("C1", 3), ("C1", 3), ("C1", 3), ("C1", 3)])
    report = {r.api_name: r for r in tracker.report()}
    assert report["C1"].held == 36
    assert report["C1"].remaining == 0  # clamped, never negative
    assert report["C1"].over_counted is True


def test_unknown_champion_is_skipped_and_recorded(tracker):
    tracker.update_source("opp1", [("C1", 1), ("GARBAGE", 2)])
    assert tracker.held()["C1"] == 1
    assert "GARBAGE" in tracker.unknown_seen
    assert "GARBAGE" not in tracker.held()


def test_held_by_source_breakdown(tracker):
    tracker.update_source("opp1", [("C1", 2)])      # 3
    tracker.update_source("opp3", [("C1", 1)])      # 1
    breakdown = tracker.held_by_source("C1")
    assert breakdown == {"opp1": 3, "opp3": 1}


def test_report_sorted_by_remaining_desc(tracker):
    tracker.update_source("opp1", [("C1", 3)])  # remove 9 from C1's 30 -> 21 left
    rows = tracker.report(sort_by="remaining")
    # C1 has 21 remaining, C2 has 25, C5 has 9 -> order C2, C1, C5
    assert [r.api_name for r in rows] == ["C2", "C1", "C5"]


def test_report_unit_objects_accepted(tracker):
    tracker.update_source("opp1", [Unit("C1", 2), {"apiName": "C2", "star": 1}])
    held = tracker.held()
    assert held["C1"] == 3
    assert held["C2"] == 1


def test_remaining_pct(tracker):
    tracker.update_source("opp1", [("C5", 3)])  # 9 of 9 gone
    report = {r.api_name: r for r in tracker.report()}
    assert report["C5"].remaining_pct == 0.0
    assert report["C2"].remaining_pct == 1.0


def test_reset(tracker):
    tracker.update_source("opp1", [("C1", 2), ("GARBAGE", 1)])
    tracker.reset()
    assert tracker.held() == {}
    assert tracker.unknown_seen == set()
