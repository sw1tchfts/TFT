"""Torch-dependent tests for the net, dataset, training, and inference.

Skipped entirely if torch isn't installed so the core suite stays light.
"""

import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

torch = pytest.importorskip("torch")

from src.model.labels import LabelSpace  # noqa: E402
from src.model.net import ChampionNet  # noqa: E402
from src.model.synth import default_portrait_dir  # noqa: E402

PORTRAITS = default_portrait_dir(17)
HAS_PORTRAITS = os.path.isdir(PORTRAITS) and any(
    f.endswith(".png") for f in os.listdir(PORTRAITS)
)
needs_portraits = pytest.mark.skipif(not HAS_PORTRAITS, reason="portraits not fetched")


def test_net_output_shapes():
    model = ChampionNet(num_classes=10, num_stars=3, width=8)
    x = torch.zeros(4, 3, 64, 64)
    clogit, slogit = model(x)
    assert clogit.shape == (4, 10)
    assert slogit.shape == (4, 3)


@needs_portraits
def test_dataset_item_types():
    from src.model.dataset import SyntheticDataset
    from src.model.synth import SyntheticGenerator

    ls = LabelSpace.from_set_data()
    gen = SyntheticGenerator(ls, PORTRAITS, size=64, seed=1)
    ds = SyntheticDataset(gen, ls, length=10)
    assert len(ds) == 10
    img, champ, star = ds[0]
    assert img.shape == (3, 64, 64)
    assert 0.0 <= float(img.min()) and float(img.max()) <= 1.0
    assert 0 <= champ < ls.num_classes
    assert 0 <= star < ls.num_stars


@needs_portraits
def test_smoke_train_and_infer(tmp_path, monkeypatch):
    """End-to-end: train a tiny model, save it, reload, recognize a crop."""
    from src.model import train as train_mod
    from src.model.synth import SyntheticGenerator

    # redirect model output dir to tmp
    monkeypatch.setattr(train_mod, "MODEL_DIR", str(tmp_path))
    metrics = train_mod.train(epochs=1, batch=16, steps=3, width=8, size=64)
    assert "champ_acc" in metrics
    assert os.path.exists(tmp_path / "classifier.pt")
    assert os.path.exists(tmp_path / "labels.json")

    from src.model.infer import ChampionRecognizer

    rec = ChampionRecognizer(
        weights_path=str(tmp_path / "classifier.pt"),
        labels_path=str(tmp_path / "labels.json"),
        device="cpu",
    )
    ls = LabelSpace.from_set_data()
    gen = SyntheticGenerator(ls, PORTRAITS, size=64, seed=11)
    crops = {f"slot{i}": gen.sample()[0] for i in range(5)}
    units = rec.recognize_slots(crops, min_confidence=0.0)
    # with min_confidence 0, every non-empty recognition becomes a Unit
    assert isinstance(units, list)
    for u in units:
        assert u.api_name in ls.classes
        assert u.star in (1, 2, 3)
