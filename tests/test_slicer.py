"""Tests for region slicing (requires numpy)."""

import os
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

np = pytest.importorskip("numpy")

from src.capture.layout import default_1024x768  # noqa: E402
from src.capture.slicer import slice_image  # noqa: E402


def _region_image(layout):
    w, h = layout.region_size
    return np.zeros((h, w, 3), dtype=np.uint8)


def test_slice_returns_all_slots():
    layout = default_1024x768()
    img = _region_image(layout)
    crops = slice_image(img, layout)
    assert set(crops) == set(layout.slot_rects())
    assert len(crops) == 42


def test_crop_shapes_match_rects():
    layout = default_1024x768()
    img = _region_image(layout)
    crops = slice_image(img, layout)
    for slot in layout.slots():
        x0, y0, x1, y1 = slot.rect
        assert crops[slot.id].shape[:2] == (y1 - y0, x1 - x0)


def test_crop_extracts_correct_pixels():
    layout = default_1024x768()
    img = _region_image(layout)
    # paint one slot's region red, verify only that crop sees red
    target = layout.slots(["shop"])[0]
    x0, y0, x1, y1 = target.rect
    img[y0:y1, x0:x1] = (255, 0, 0)
    crops = slice_image(img, layout)
    assert (crops[target.id] == (255, 0, 0)).all()
    # a far-away slot should be untouched
    other = layout.slots(["board"])[0]
    assert (crops[other.id] == 0).all()


def test_size_mismatch_raises():
    layout = default_1024x768()
    bad = np.zeros((100, 100, 3), dtype=np.uint8)
    with pytest.raises(ValueError):
        slice_image(bad, layout)


def test_group_filter():
    layout = default_1024x768()
    img = _region_image(layout)
    crops = slice_image(img, layout, groups=["bench"])
    assert len(crops) == 9
    assert all(k.startswith("bench:") for k in crops)
