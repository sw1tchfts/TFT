"""Synthetic training-image generator for the champion classifier.

We never hand-label screenshots. Instead we composite labeled training crops
from the champion HUD portraits downloaded by `fetch_data.py`:

    background (tinted by cost tier) + portrait (scaled/rotated/jittered)
    + star pips (1/2/3, colored by tier) + photometric augmentation

Plus an EMPTY class (background only) so the model can recognize empty slots.

Output crops are uint8 RGB at a fixed size, matching what the model consumes.
Everything is seedable for reproducible datasets and tests. Pure numpy + PIL.
"""

from __future__ import annotations

import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

from .labels import EMPTY, STAR_LEVELS, LabelSpace

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Star pip colors by level: 1=bronze, 2=silver, 3=gold.
STAR_COLORS = {1: (205, 127, 50), 2: (200, 200, 210), 3: (255, 215, 0)}

# Loose cost-tier border tints (used to color backgrounds so the model doesn't
# overfit to a single background). Exact in-game colors can be calibrated later.
COST_TINTS = {
    1: (120, 120, 120),
    2: (40, 140, 60),
    3: (40, 90, 180),
    4: (150, 50, 170),
    5: (200, 160, 40),
}


class SampleSpec:
    """A label triple for one generated crop."""

    __slots__ = ("api_name", "star", "cost")

    def __init__(self, api_name: str, star: int, cost: int):
        self.api_name = api_name
        self.star = star
        self.cost = cost

    @property
    def is_empty(self) -> bool:
        return self.api_name == EMPTY


class SyntheticGenerator:
    def __init__(
        self,
        labels: LabelSpace,
        portrait_dir: str,
        size: int = 64,
        empty_ratio: float = 0.12,
        seed: int | None = None,
    ):
        self.labels = labels
        self.size = size
        self.empty_ratio = empty_ratio
        self.rng = np.random.default_rng(seed)
        self._portraits: dict[str, Image.Image] = {}
        self._costs: dict[str, int] = {}
        self._load_portraits(portrait_dir)
        if not self._portraits:
            raise RuntimeError(f"no portraits found in {portrait_dir}")
        self._champ_pool = list(self._portraits)

    def _load_portraits(self, portrait_dir: str) -> None:
        # cost lookup from set_data via the label classes order isn't enough;
        # read costs from the portraits' filenames mapped through set_data.
        costs = _load_costs()
        for api_name in self.labels.classes:
            if api_name == EMPTY:
                continue
            fname = f"{api_name.lower()}.png"
            path = os.path.join(portrait_dir, fname)
            if os.path.exists(path):
                img = Image.open(path).convert("RGB")
                self._portraits[api_name] = img
                self._costs[api_name] = costs.get(api_name, 1)

    # -- sampling ----------------------------------------------------------

    def sample_spec(self) -> SampleSpec:
        if self.rng.random() < self.empty_ratio:
            return SampleSpec(EMPTY, 1, 0)
        api = self._champ_pool[self.rng.integers(len(self._champ_pool))]
        # 3-star rarer than 1/2-star
        star = int(self.rng.choice(STAR_LEVELS, p=[0.5, 0.35, 0.15]))
        return SampleSpec(api, star, self._costs.get(api, 1))

    # -- rendering ---------------------------------------------------------

    def _background(self, cost: int) -> Image.Image:
        s = self.size
        base = self.rng.integers(15, 60, size=3)
        tint = np.array(COST_TINTS.get(cost, (90, 90, 90)))
        mix = self.rng.uniform(0.0, 0.45)
        color = (base * (1 - mix) + tint * mix).clip(0, 255).astype(np.uint8)
        arr = np.tile(color, (s, s, 1)).astype(np.uint8)
        # add a soft vertical gradient + noise for variety
        grad = np.linspace(-25, 25, s).astype(np.int16)[:, None, None]
        arr = (arr.astype(np.int16) + grad).clip(0, 255).astype(np.uint8)
        return Image.fromarray(arr)

    def _paste_portrait(self, bg: Image.Image, spec: SampleSpec) -> Image.Image:
        portrait = self._portraits[spec.api_name]
        s = self.size
        scale = self.rng.uniform(0.82, 1.08)
        side = max(8, int(s * scale))
        p = portrait.resize((side, side), Image.BILINEAR)
        angle = self.rng.uniform(-7, 7)
        p = p.rotate(angle, resample=Image.BILINEAR, expand=False)
        # position jitter
        max_off = max(0, s - side)
        ox = int(self.rng.integers(-4, 5)) + (max_off // 2 if max_off else 0)
        oy = int(self.rng.integers(-4, 5)) + (max_off // 2 if max_off else 0)
        canvas = bg.copy()
        canvas.paste(p, (ox - (side - s) // 2 if side > s else ox,
                         oy - (side - s) // 2 if side > s else oy))
        return canvas

    def _draw_stars(self, img: Image.Image, star: int) -> Image.Image:
        draw = ImageDraw.Draw(img)
        s = self.size
        color = STAR_COLORS[star]
        pip = max(2, s // 16)
        gap = pip + 2
        total = star * gap
        x = (s - total) // 2 + gap // 2
        y = max(1, int(s * 0.06))
        for _ in range(star):
            self._draw_star(draw, x, y, pip, color)
            x += gap
        return img

    @staticmethod
    def _draw_star(draw: ImageDraw.ImageDraw, cx: int, cy: int, r: int, color):
        pts = []
        for i in range(10):
            ang = -math.pi / 2 + i * math.pi / 5
            rr = r if i % 2 == 0 else r * 0.45
            pts.append((cx + rr * math.cos(ang), cy + rr * math.sin(ang)))
        draw.polygon(pts, fill=color)

    def _augment(self, img: Image.Image) -> Image.Image:
        img = ImageEnhance.Brightness(img).enhance(self.rng.uniform(0.75, 1.25))
        img = ImageEnhance.Contrast(img).enhance(self.rng.uniform(0.8, 1.2))
        if self.rng.random() < 0.3:
            img = img.filter(ImageFilter.GaussianBlur(self.rng.uniform(0.3, 0.9)))
        arr = np.asarray(img).astype(np.int16)
        noise = self.rng.normal(0, self.rng.uniform(2, 10), arr.shape)
        arr = (arr + noise).clip(0, 255).astype(np.uint8)
        return Image.fromarray(arr)

    def render(self, spec: SampleSpec) -> np.ndarray:
        bg = self._background(spec.cost)
        if spec.is_empty:
            img = self._augment(bg)
            return np.asarray(img)
        img = self._paste_portrait(bg, spec)
        img = self._draw_stars(img, spec.star)
        img = self._augment(img)
        return np.asarray(img)

    def sample(self) -> tuple[np.ndarray, SampleSpec]:
        spec = self.sample_spec()
        return self.render(spec), spec

    def batch(self, n: int) -> tuple[np.ndarray, list[SampleSpec]]:
        imgs, specs = [], []
        for _ in range(n):
            img, spec = self.sample()
            imgs.append(img)
            specs.append(spec)
        return np.stack(imgs), specs


def _load_costs() -> dict[str, int]:
    import json

    path = os.path.join(REPO_ROOT, "config", "set_data.json")
    try:
        with open(path) as fh:
            data = json.load(fh)
        return {c["apiName"]: int(c["cost"]) for c in data["champions"]}
    except FileNotFoundError:
        return {}


def default_portrait_dir(set_number: int = 17) -> str:
    return os.path.join(REPO_ROOT, "assets", "portraits", f"set{set_number}")
