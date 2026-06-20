"""Tests for the label space and synthetic generator (no torch needed)."""

import os
import sys

import numpy as np
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.model.labels import EMPTY, STAR_LEVELS, LabelSpace  # noqa: E402
from src.model.synth import (  # noqa: E402
    SampleSpec,
    SyntheticGenerator,
    default_portrait_dir,
)

PORTRAITS = default_portrait_dir(17)
HAS_PORTRAITS = os.path.isdir(PORTRAITS) and any(
    f.endswith(".png") for f in os.listdir(PORTRAITS)
)
needs_portraits = pytest.mark.skipif(not HAS_PORTRAITS, reason="portraits not fetched")


# -- label space -----------------------------------------------------------

def test_label_space_empty_is_zero():
    ls = LabelSpace(["B", "A", "C"])
    assert ls.classes[0] == EMPTY
    assert ls.empty_index == 0
    # champions sorted after EMPTY
    assert ls.classes == [EMPTY, "A", "B", "C"]


def test_label_roundtrip_indices():
    ls = LabelSpace(["A", "B"])
    for name in ["A", "B"]:
        assert ls.idx_to_champ(ls.champ_to_idx(name)) == name
    for star in STAR_LEVELS:
        assert ls.idx_to_star(ls.star_to_idx(star)) == star


def test_label_space_from_set_data():
    ls = LabelSpace.from_set_data()
    assert ls.num_classes == 64  # 63 champions + EMPTY
    assert ls.num_stars == 3
    assert ls.is_empty(0)


def test_label_space_save_load(tmp_path):
    ls = LabelSpace(["X", "Y", "Z"])
    p = tmp_path / "labels.json"
    ls.save(str(p))
    loaded = LabelSpace.load(str(p))
    assert loaded.classes == ls.classes
    assert loaded.empty_index == ls.empty_index


# -- synthetic generator ---------------------------------------------------

@needs_portraits
def test_generator_loads_all_portraits():
    ls = LabelSpace.from_set_data()
    gen = SyntheticGenerator(ls, PORTRAITS, size=64, seed=1)
    assert len(gen._champ_pool) == 63


@needs_portraits
def test_sample_shape_and_dtype():
    ls = LabelSpace.from_set_data()
    gen = SyntheticGenerator(ls, PORTRAITS, size=48, seed=1)
    img, spec = gen.sample()
    assert img.shape == (48, 48, 3)
    assert img.dtype == np.uint8


@needs_portraits
def test_determinism_with_seed():
    ls = LabelSpace.from_set_data()
    a = SyntheticGenerator(ls, PORTRAITS, size=64, seed=123).sample()[0]
    b = SyntheticGenerator(ls, PORTRAITS, size=64, seed=123).sample()[0]
    assert np.array_equal(a, b)


@needs_portraits
def test_empty_samples_appear():
    ls = LabelSpace.from_set_data()
    gen = SyntheticGenerator(ls, PORTRAITS, size=64, empty_ratio=1.0, seed=2)
    specs = [gen.sample_spec() for _ in range(20)]
    assert all(s.is_empty for s in specs)


@needs_portraits
def test_star_levels_in_range():
    ls = LabelSpace.from_set_data()
    gen = SyntheticGenerator(ls, PORTRAITS, size=64, empty_ratio=0.0, seed=3)
    for _ in range(50):
        spec = gen.sample_spec()
        assert spec.star in STAR_LEVELS


@needs_portraits
def test_render_specific_spec_is_repeatable():
    ls = LabelSpace.from_set_data()
    api = sorted(ls.classes)[1]  # a real champion
    spec = SampleSpec(api, 2, 1)
    g1 = SyntheticGenerator(ls, PORTRAITS, size=64, seed=5)
    g2 = SyntheticGenerator(ls, PORTRAITS, size=64, seed=5)
    assert np.array_equal(g1.render(spec), g2.render(spec))


@needs_portraits
def test_batch_returns_aligned_specs():
    ls = LabelSpace.from_set_data()
    gen = SyntheticGenerator(ls, PORTRAITS, size=32, seed=9)
    imgs, specs = gen.batch(8)
    assert imgs.shape == (8, 32, 32, 3)
    assert len(specs) == 8
