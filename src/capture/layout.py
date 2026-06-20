"""Slot geometry for slicing a captured TFT region into unit cells.

The capture region (the TFT play area inside the windowed client) is described
once via drag-calibration. Within that region, three grids locate the unit
slots:

    board  - the 4x7 hex grid (staggered rows)
    bench  - 1x9 row of bench slots
    shop   - 1x5 row of shop slots (only on your own screen)

All positions are stored as **fractions of the region** so a single layout file
scales to any region size; pixel rectangles are derived on demand. Rectangles
returned here are **region-local** (origin 0,0 = region top-left), which is what
the slicer needs because the screen grab already contains only the region. Use
`Layout.to_screen` to convert a local rect to absolute screen coordinates for
capture.

This module is pure standard library so the geometry is fast to import and fully
unit-testable without a display.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, asdict, field

# Pixel rectangle as (x0, y0, x1, y1).
Rect = tuple[int, int, int, int]


@dataclass(frozen=True)
class Slot:
    id: str
    group: str
    row: int
    col: int
    rect: Rect  # region-local pixels (x0, y0, x1, y1)

    @property
    def width(self) -> int:
        return self.rect[2] - self.rect[0]

    @property
    def height(self) -> int:
        return self.rect[3] - self.rect[1]


@dataclass
class SlotGroup:
    """A regular grid of slots positioned by fractions of the region.

    origin       : (fx, fy) center of cell (row 0, col 0)
    col_pitch    : (dfx, dfy) added per column step
    row_pitch    : (dfx, dfy) added per row step
    row_stagger  : extra fx applied to odd-numbered rows (hex offset)
    cell_size    : (fw, fh) crop box size
    """

    rows: int
    cols: int
    origin: tuple[float, float]
    col_pitch: tuple[float, float]
    row_pitch: tuple[float, float]
    cell_size: tuple[float, float]
    row_stagger: float = 0.0

    def cell_center(self, row: int, col: int) -> tuple[float, float]:
        fx = (
            self.origin[0]
            + col * self.col_pitch[0]
            + row * self.row_pitch[0]
            + (row % 2) * self.row_stagger
        )
        fy = (
            self.origin[1]
            + col * self.col_pitch[1]
            + row * self.row_pitch[1]
        )
        return fx, fy


@dataclass
class Layout:
    resolution: str
    region: Rect  # screen-space capture rect (x0, y0, x1, y1)
    groups: dict[str, SlotGroup] = field(default_factory=dict)

    # -- region helpers ----------------------------------------------------

    @property
    def region_size(self) -> tuple[int, int]:
        x0, y0, x1, y1 = self.region
        return x1 - x0, y1 - y0

    def to_screen(self, local_rect: Rect) -> Rect:
        x0, y0, x1, y1 = local_rect
        rx, ry = self.region[0], self.region[1]
        return rx + x0, ry + y0, rx + x1, ry + y1

    # -- slot computation --------------------------------------------------

    def _cell_rect(self, group: SlotGroup, row: int, col: int) -> Rect:
        w, h = self.region_size
        cfx, cfy = group.cell_center(row, col)
        cx, cy = cfx * w, cfy * h
        cw, ch = group.cell_size[0] * w, group.cell_size[1] * h
        x0 = int(round(cx - cw / 2))
        y0 = int(round(cy - ch / 2))
        x1 = int(round(cx + cw / 2))
        y1 = int(round(cy + ch / 2))
        # clamp to region bounds
        x0, y0 = max(0, x0), max(0, y0)
        x1, y1 = min(w, x1), min(h, y1)
        return x0, y0, x1, y1

    def slots(self, groups: list[str] | None = None) -> list[Slot]:
        names = groups if groups is not None else list(self.groups)
        out: list[Slot] = []
        for name in names:
            group = self.groups[name]
            for row in range(group.rows):
                for col in range(group.cols):
                    rect = self._cell_rect(group, row, col)
                    out.append(
                        Slot(
                            id=f"{name}:{row},{col}",
                            group=name,
                            row=row,
                            col=col,
                            rect=rect,
                        )
                    )
        return out

    def slot_rects(self, groups: list[str] | None = None) -> dict[str, Rect]:
        return {s.id: s.rect for s in self.slots(groups)}

    # -- serialization -----------------------------------------------------

    def to_dict(self) -> dict:
        return {
            "resolution": self.resolution,
            "region": list(self.region),
            "groups": {name: asdict(g) for name, g in self.groups.items()},
        }

    def save(self, path: str) -> None:
        with open(path, "w") as fh:
            json.dump(self.to_dict(), fh, indent=2)
            fh.write("\n")

    @classmethod
    def from_dict(cls, d: dict) -> "Layout":
        groups = {}
        for name, g in d.get("groups", {}).items():
            groups[name] = SlotGroup(
                rows=g["rows"],
                cols=g["cols"],
                origin=tuple(g["origin"]),
                col_pitch=tuple(g["col_pitch"]),
                row_pitch=tuple(g["row_pitch"]),
                cell_size=tuple(g["cell_size"]),
                row_stagger=g.get("row_stagger", 0.0),
            )
        return cls(
            resolution=d["resolution"],
            region=tuple(d["region"]),
            groups=groups,
        )

    @classmethod
    def load(cls, path: str) -> "Layout":
        with open(path) as fh:
            return cls.from_dict(json.load(fh))


def default_1024x768() -> Layout:
    """Placeholder layout for a 1024x768 windowed client.

    The fractions below are reasonable starting estimates, NOT measured pixels.
    Run the calibration tool (src.capture.calibrate) to set the real region and
    fine-tune the grids against an actual screenshot before relying on slicing.
    """
    return Layout(
        resolution="1024x768",
        region=(0, 0, 1024, 768),
        groups={
            # 4x7 staggered hex grid
            "board": SlotGroup(
                rows=4,
                cols=7,
                origin=(0.305, 0.190),
                col_pitch=(0.0590, 0.0),
                row_pitch=(0.0, 0.1080),
                cell_size=(0.050, 0.070),
                row_stagger=0.0295,
            ),
            # 1x9 bench
            "bench": SlotGroup(
                rows=1,
                cols=9,
                origin=(0.180, 0.730),
                col_pitch=(0.0640, 0.0),
                row_pitch=(0.0, 0.0),
                cell_size=(0.050, 0.070),
            ),
            # 1x5 shop (own screen only)
            "shop": SlotGroup(
                rows=1,
                cols=5,
                origin=(0.300, 0.930),
                col_pitch=(0.0880, 0.0),
                row_pitch=(0.0, 0.0),
                cell_size=(0.060, 0.080),
            ),
        },
    )
