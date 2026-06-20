"""Tests for slot geometry (pure, no display)."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.capture.layout import Layout, SlotGroup, default_1024x768  # noqa: E402


def test_default_slot_counts():
    layout = default_1024x768()
    slots = layout.slots()
    by_group = {}
    for s in slots:
        by_group[s.group] = by_group.get(s.group, 0) + 1
    assert by_group == {"board": 28, "bench": 9, "shop": 5}
    assert len(slots) == 42


def test_slot_ids_unique_and_formatted():
    layout = default_1024x768()
    ids = [s.id for s in layout.slots()]
    assert len(ids) == len(set(ids))
    assert "board:0,0" in ids
    assert "board:3,6" in ids
    assert "bench:0,8" in ids
    assert "shop:0,4" in ids


def test_rects_within_region_bounds():
    layout = default_1024x768()
    w, h = layout.region_size
    for s in layout.slots():
        x0, y0, x1, y1 = s.rect
        assert 0 <= x0 < x1 <= w
        assert 0 <= y0 < y1 <= h


def test_columns_increase_left_to_right():
    layout = default_1024x768()
    rects = layout.slot_rects(["bench"])
    xs = [rects[f"bench:0,{c}"][0] for c in range(9)]
    assert xs == sorted(xs)
    assert len(set(xs)) == 9  # strictly increasing, no overlap collapse


def test_rows_increase_top_to_bottom():
    layout = default_1024x768()
    rects = layout.slot_rects(["board"])
    ys = [rects[f"board:{r},0"][1] for r in range(4)]
    assert ys == sorted(ys)


def test_odd_rows_are_staggered():
    layout = default_1024x768()
    rects = layout.slot_rects(["board"])
    even_x = rects["board:0,0"][0]
    odd_x = rects["board:1,0"][0]
    assert odd_x > even_x  # row 1 shifted right by the hex stagger


def test_groups_filter():
    layout = default_1024x768()
    assert {s.group for s in layout.slots(["shop"])} == {"shop"}
    assert len(layout.slots(["shop"])) == 5


def test_to_screen_offsets_by_region_origin():
    layout = default_1024x768()
    layout.region = (100, 50, 100 + 1024, 50 + 768)
    local = (10, 20, 30, 40)
    assert layout.to_screen(local) == (110, 70, 130, 90)


def test_geometry_scales_with_region():
    """Same fractions, bigger region -> proportionally larger/offset rects."""
    base = default_1024x768()
    big = default_1024x768()
    big.region = (0, 0, 2048, 1536)  # 2x
    b = base.slot_rects(["shop"])["shop:0,0"]
    g = big.slot_rects(["shop"])["shop:0,0"]
    # centers should roughly double
    bc = ((b[0] + b[2]) / 2, (b[1] + b[3]) / 2)
    gc = ((g[0] + g[2]) / 2, (g[1] + g[3]) / 2)
    assert abs(gc[0] - bc[0] * 2) <= 2
    assert abs(gc[1] - bc[1] * 2) <= 2


def test_roundtrip_serialization(tmp_path):
    layout = default_1024x768()
    layout.region = (5, 6, 5 + 1024, 6 + 768)
    path = tmp_path / "layout.json"
    layout.save(str(path))
    loaded = Layout.load(str(path))
    assert loaded.region == layout.region
    assert loaded.resolution == layout.resolution
    assert loaded.slot_rects() == layout.slot_rects()


def test_cell_center_math():
    group = SlotGroup(
        rows=1, cols=2,
        origin=(0.5, 0.5),
        col_pitch=(0.1, 0.0),
        row_pitch=(0.0, 0.0),
        cell_size=(0.1, 0.1),
    )
    assert group.cell_center(0, 0) == (0.5, 0.5)
    assert group.cell_center(0, 1) == (0.6, 0.5)
