"""Slice a captured region image into per-slot crops using a Layout.

The input image is the region grab (region-local coordinates), so slot rects
from `Layout` apply directly. Output crops feed the vision classifier.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from .layout import Layout

if TYPE_CHECKING:  # avoid hard numpy dependency at import time for type checkers
    import numpy as np


def slice_image(image, layout: Layout, groups: list[str] | None = None) -> dict:
    """Return {slot_id: crop} for every slot in the requested groups.

    `image` is an (H, W) or (H, W, C) numpy array sized to the layout region.
    Crops are views into `image` (no copy); copy downstream if you mutate them.
    Slots whose rect has zero area (fully clamped out of frame) are skipped.
    """
    h, w = image.shape[0], image.shape[1]
    rw, rh = layout.region_size
    if (w, h) != (rw, rh):
        raise ValueError(
            f"image size {(w, h)} does not match layout region {(rw, rh)}; "
            "grab the region exactly or rescale before slicing"
        )

    crops: dict = {}
    for slot in layout.slots(groups):
        x0, y0, x1, y1 = slot.rect
        if x1 <= x0 or y1 <= y0:
            continue
        crops[slot.id] = image[y0:y1, x0:x1]
    return crops


def save_crops(crops: dict, out_dir: str) -> int:
    """Write each slot crop to out_dir as a PNG (for calibration checks)."""
    import os

    from PIL import Image

    os.makedirs(out_dir, exist_ok=True)
    for slot_id, crop in crops.items():
        fname = slot_id.replace(":", "_").replace(",", "-") + ".png"
        Image.fromarray(crop).save(os.path.join(out_dir, fname))
    return len(crops)
