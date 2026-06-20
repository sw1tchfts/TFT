"""Torch dataset wrapping the synthetic generator.

Map-style dataset of fixed length per epoch; each item is generated fresh, so
"epochs" are just sampling budgets over an effectively infinite synthetic
distribution. Returns (image CxHxW float in [0,1], champ_idx, star_idx).
"""

from __future__ import annotations

import numpy as np
import torch
from torch.utils.data import Dataset

from .labels import LabelSpace
from .synth import SyntheticGenerator


def to_tensor(img_uint8: np.ndarray) -> torch.Tensor:
    """HxWx3 uint8 -> 3xHxW float in [0,1]."""
    # copy() so the tensor owns writable memory (PIL arrays are read-only)
    t = torch.from_numpy(np.ascontiguousarray(img_uint8).copy()).float() / 255.0
    return t.permute(2, 0, 1)


class SyntheticDataset(Dataset):
    def __init__(self, generator: SyntheticGenerator, labels: LabelSpace,
                 length: int):
        self.gen = generator
        self.labels = labels
        self.length = length

    def __len__(self) -> int:
        return self.length

    def __getitem__(self, _idx: int):
        img, spec = self.gen.sample()
        champ_idx = self.labels.champ_to_idx(spec.api_name)
        star_idx = self.labels.star_to_idx(spec.star)
        return to_tensor(img), champ_idx, star_idx
