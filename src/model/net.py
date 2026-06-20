"""Multi-task CNN: champion classification + star-level head.

Small enough to train on CPU from synthetic data and to run per-slot in real
time. Two heads share a convolutional trunk:
    - champ head: num_classes logits (includes the EMPTY class)
    - star head : 3 logits (1/2/3 star); ignored for empty slots at train time
"""

from __future__ import annotations

import torch
import torch.nn as nn


def _block(cin: int, cout: int) -> nn.Sequential:
    return nn.Sequential(
        nn.Conv2d(cin, cout, 3, padding=1, bias=False),
        nn.BatchNorm2d(cout),
        nn.ReLU(inplace=True),
        nn.MaxPool2d(2),
    )


class ChampionNet(nn.Module):
    def __init__(self, num_classes: int, num_stars: int = 3, width: int = 32):
        super().__init__()
        self.trunk = nn.Sequential(
            _block(3, width),         # 64 -> 32
            _block(width, width * 2),  # 32 -> 16
            _block(width * 2, width * 4),  # 16 -> 8
            _block(width * 4, width * 4),  # 8 -> 4
            nn.AdaptiveAvgPool2d(1),
        )
        feat = width * 4
        self.champ_head = nn.Linear(feat, num_classes)
        self.star_head = nn.Linear(feat, num_stars)

    def forward(self, x: torch.Tensor):
        f = self.trunk(x).flatten(1)
        return self.champ_head(f), self.star_head(f)
