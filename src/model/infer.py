"""Inference: recognize champion + star from slot crops.

Bridges the vision model to the pool engine: given the per-slot crops produced
by the slicer, returns the list of Units (api_name, star) for non-empty,
confident slots — ready to feed into PoolTracker.update_source.
"""

from __future__ import annotations

import os
from dataclasses import dataclass

import numpy as np

from ..engine.pool import Unit
from .labels import LabelSpace
from .net import ChampionNet

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
MODEL_DIR = os.path.join(REPO_ROOT, "models")


@dataclass
class Recognition:
    api_name: str | None  # None == empty slot
    star: int
    confidence: float

    @property
    def is_empty(self) -> bool:
        return self.api_name is None


class ChampionRecognizer:
    def __init__(self, weights_path: str | None = None,
                 labels_path: str | None = None, device: str | None = None):
        import torch

        self.torch = torch
        self.device = device or ("cuda" if torch.cuda.is_available() else "cpu")
        weights_path = weights_path or os.path.join(MODEL_DIR, "classifier.pt")
        labels_path = labels_path or os.path.join(MODEL_DIR, "labels.json")
        ckpt = torch.load(weights_path, map_location=self.device)
        self.labels = LabelSpace.load(labels_path)
        self.size = ckpt.get("size", 64)
        self.model = ChampionNet(
            ckpt["num_classes"], ckpt["num_stars"], width=ckpt.get("width", 32)
        ).to(self.device)
        self.model.load_state_dict(ckpt["state_dict"])
        self.model.eval()

    # -- preprocessing -----------------------------------------------------

    def _preprocess(self, crops: list[np.ndarray]):
        from PIL import Image

        tensors = []
        for c in crops:
            img = Image.fromarray(c).convert("RGB").resize(
                (self.size, self.size), Image.BILINEAR
            )
            arr = np.asarray(img).astype(np.float32) / 255.0
            tensors.append(self.torch.from_numpy(arr).permute(2, 0, 1))
        return self.torch.stack(tensors).to(self.device)

    # -- recognition -------------------------------------------------------

    def recognize_batch(self, crops: list[np.ndarray]) -> list[Recognition]:
        if not crops:
            return []
        x = self._preprocess(crops)
        with self.torch.no_grad():
            clogit, slogit = self.model(x)
            cprob = clogit.softmax(1)
            conf, cidx = cprob.max(1)
            sidx = slogit.argmax(1)
        out = []
        for i in range(len(crops)):
            ci = int(cidx[i])
            if self.labels.is_empty(ci):
                out.append(Recognition(None, 1, float(conf[i])))
            else:
                out.append(
                    Recognition(
                        self.labels.idx_to_champ(ci),
                        self.labels.idx_to_star(int(sidx[i])),
                        float(conf[i]),
                    )
                )
        return out

    def recognize_slots(self, crops: dict[str, np.ndarray],
                        min_confidence: float = 0.5) -> list[Unit]:
        """Map {slot_id: crop} -> [Unit] for confident, non-empty slots."""
        ids = list(crops)
        results = self.recognize_batch([crops[i] for i in ids])
        units: list[Unit] = []
        for rec in results:
            if rec.is_empty or rec.confidence < min_confidence:
                continue
            units.append(Unit(rec.api_name, rec.star))
        return units
